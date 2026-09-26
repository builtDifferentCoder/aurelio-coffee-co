import json
import os
import re
from typing import Any, Dict, List

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.prompts import RAG_ANSWER_PROMPT, ROUTER_CLASSIFICATION_PROMPT
from app.agent.state import AgentState
from app.core.config import settings
from app.rag.retriever import retrieve
from app.tools.definitions import AURELIO_TOOLS

# Fixed responses
ESCALATION_MESSAGE = "I'm connecting you with a support specialist who can help with this."
OFF_TOPIC_MESSAGE = (
    "I'm here to help with Aurelio Coffee questions — orders, subscriptions, "
    "products, and policies. What can I help with?"
)

# Hardcoded escalation triggers
ESCALATION_KEYWORDS = [
    "refund",
    "damaged",
    "lost",
    "human",
    "agent",
    "speak to someone",
    "cancel and charge",
    "money back",
    "get my money",
    "want my money",
]


def get_model(temperature: float = 0):
    """Instantiate Claude Haiku model using configured environment settings."""
    model_name = os.getenv("MODEL_NAME", settings.MODEL_NAME)
    api_key = os.getenv("ANTHROPIC_API_KEY", settings.ANTHROPIC_API_KEY)
    return ChatAnthropic(
        model=model_name,
        api_key=api_key,
        temperature=temperature,
    )


def _get_latest_user_text(messages: List[Any]) -> str:
    """Extract string content of the latest user message."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
        if isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            return str(msg.get("content", ""))
        if hasattr(msg, "content") and not isinstance(msg, (AIMessage, ToolMessage, SystemMessage)):
            return str(msg.content)
    return ""


def router_node(state: AgentState) -> Dict[str, Any]:
    """
    Classify user message into 'escalate', 'rag', 'tool', or 'off_topic'.
    First checks hardcoded escalation keywords to skip LLM entirely.
    """
    messages = state.get("messages", [])
    user_text = _get_latest_user_text(messages)
    lower_text = user_text.lower()

    # 1. Hardcoded keyword check for immediate escalation
    if any(keyword in lower_text for keyword in ESCALATION_KEYWORDS):
        return {"intent": "escalate"}

    # Pattern check: "cancel" co-occurring with "refund", "money", or "back" anywhere in the message
    if re.search(r"\bcancel\w*\b.*?\b(refund|money|back)\b|\b(refund|money|back)\b.*?\bcancel\w*\b", lower_text, re.DOTALL):
        return {"intent": "escalate"}

    # 2. Otherwise classify via Claude Haiku
    model = get_model(temperature=0)
    classification_response = model.invoke([
        SystemMessage(content=ROUTER_CLASSIFICATION_PROMPT),
        HumanMessage(content=user_text),
    ])

    raw_intent = str(classification_response.content).strip().lower()
    if "tool" in raw_intent:
        intent = "tool"
    elif "off_topic" in raw_intent or "off-topic" in raw_intent or "off topic" in raw_intent:
        intent = "off_topic"
    elif "rag" in raw_intent:
        intent = "rag"
    else:
        intent = "rag"

    return {"intent": intent}


def rag_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieve knowledge base documents and generate a grounded answer with Haiku.
    If no documents meet the min_confidence threshold, redirect to off_topic.
    """
    messages = state.get("messages", [])
    user_text = _get_latest_user_text(messages)

    retrieved = retrieve(query=user_text, k=3, min_confidence=1.3)

    if not retrieved:
        # Fall back to off_topic redirect if no relevant knowledge found
        return {
            "intent": "off_topic",
            "retrieved_context": [],
            "messages": [AIMessage(content=OFF_TOPIC_MESSAGE)],
        }

    # Format context for grounding
    context_blocks = []
    for doc in retrieved:
        title = doc.get("metadata", {}).get("title", "Reference")
        context_blocks.append(f"[{title}]\n{doc.get('text', '')}")
    formatted_context = "\n\n---\n\n".join(context_blocks)

    system_instruction = RAG_ANSWER_PROMPT.format(context=formatted_context)

    model = get_model(temperature=0.2)
    conversation_to_send = [SystemMessage(content=system_instruction)] + list(messages)
    answer = model.invoke(conversation_to_send)

    return {
        "intent": "rag",
        "retrieved_context": retrieved,
        "messages": [answer],
    }


def tool_node(state: AgentState) -> Dict[str, Any]:
    """
    Bind tools to Haiku, let Haiku decide the tool call, execute the tool,
    and generate a natural language response incorporating the tool result.
    Handles simulated errors gracefully.
    """
    messages = state.get("messages", [])
    tool_map = {t.name: t for t in AURELIO_TOOLS}

    model = get_model(temperature=0)
    model_with_tools = model.bind_tools(AURELIO_TOOLS)

    tool_call_response = model_with_tools.invoke(messages)

    # Check if a tool call was issued
    if not tool_call_response.tool_calls:
        return {
            "intent": "tool",
            "tool_result": None,
            "messages": [tool_call_response],
        }

    # Execute every tool call and construct a ToolMessage for EACH tool_use_id
    tool_messages = []
    tool_outputs = []

    for tool_call in tool_call_response.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        call_id = tool_call["id"]

        selected_tool = tool_map.get(tool_name)
        if selected_tool:
            try:
                tool_output = selected_tool.invoke(tool_args)
            except Exception as err:
                tool_output = {"error": "tool_execution_failed", "message": str(err)}
        else:
            tool_output = {"error": "unknown_tool", "message": f"Tool '{tool_name}' not found."}

        tool_outputs.append(tool_output)
        tool_messages.append(
            ToolMessage(
                content=json.dumps(tool_output),
                tool_call_id=call_id,
            )
        )

    system_tool_prompt = SystemMessage(
        content=(
            "You are an Aurelio Coffee Co. support assistant. Explain the tool output(s) "
            "warmly and clearly to the customer. If any tool output contains an error "
            "(such as a service timeout), apologize graciously and suggest retrying in a moment "
            "or offering to connect them with a human specialist."
        )
    )

    final_conversation = [system_tool_prompt] + list(messages) + [tool_call_response] + tool_messages
    final_response = model.invoke(final_conversation)

    primary_result = tool_outputs[0] if len(tool_outputs) == 1 else {"results": tool_outputs}

    return {
        "intent": "tool",
        "tool_result": primary_result,
        "messages": [tool_call_response] + tool_messages + [final_response],
    }


def escalation_node(state: AgentState) -> Dict[str, Any]:
    """Return fixed, non-LLM escalation response."""
    return {
        "intent": "escalate",
        "retrieved_context": [],
        "messages": [
            AIMessage(
                content=ESCALATION_MESSAGE,
                additional_kwargs={"escalated": True},
            )
        ],
    }


def off_topic_node(state: AgentState) -> Dict[str, Any]:
    """Return fixed, non-LLM off-topic redirect response."""
    return {
        "intent": "off_topic",
        "retrieved_context": [],
        "messages": [AIMessage(content=OFF_TOPIC_MESSAGE)],
    }
