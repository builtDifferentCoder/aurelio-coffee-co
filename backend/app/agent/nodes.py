import json
import os
import re
from typing import Any, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.prompts import RAG_ANSWER_PROMPT, ROUTER_CLASSIFICATION_PROMPT
from app.agent.state import AgentState
from app.core.config import settings
from app.rag.retriever import retrieve
from app.tools import mock_api
from app.tools.definitions import AURELIO_TOOLS

# Fixed responses
ESCALATION_MESSAGE = "I'm connecting you with a support specialist who can help with this."
OFF_TOPIC_MESSAGE = (
    "I'm here to help with Aurelio Coffee questions — orders, subscriptions, "
    "products, and policies. What can I help with?"
)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+")


def _extract_email_from_text(text: str) -> Optional[str]:
    """Extract first email address from a string, stripping any trailing punctuation."""
    match = EMAIL_REGEX.search(text)
    if not match:
        return None
    cleaned = match.group(0).rstrip(".,;:!?'\"()[]{}").strip().lower()
    return cleaned if cleaned else None


def _extract_recent_email(messages: List[Any]) -> Optional[str]:
    """Inspect recent messages in reverse order to find any customer email."""
    for msg in reversed(messages):
        content = ""
        if isinstance(msg, HumanMessage):
            content = str(msg.content)
        elif isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            content = str(msg.get("content", ""))
        elif hasattr(msg, "content") and not isinstance(msg, (AIMessage, ToolMessage, SystemMessage)):
            content = str(msg.content)
        email = _extract_email_from_text(content)
        if email:
            return email
    return None


def _needs_customer_lookup(user_text: str) -> bool:
    """Determine whether a tool request requires personal order or subscription lookup."""
    lower = user_text.lower()
    # General pricing questions do not need personal lookup
    is_general_pricing = any(k in lower for k in ["how much", "pricing", "compare", "plans"]) and not any(
        k in lower for k in ["my order", "ord-", "my subscription", "pause", "status", "cancel"]
    )
    if is_general_pricing:
        return False

    lookup_keywords = [
        "order",
        "ord-",
        "tracking",
        "subscription",
        "pause",
        "shipment",
        "deliver",
        "package",
    ]
    return any(k in lower for k in lookup_keywords)

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
    customer_email = state.get("customer_email") or _extract_recent_email(messages)

    # 1. Hardcoded keyword check for immediate escalation
    if any(keyword in lower_text for keyword in ESCALATION_KEYWORDS):
        return {"intent": "escalate", "customer_email": customer_email}

    # Pattern check: "cancel" co-occurring with "refund", "money", or "back" anywhere in the message
    if re.search(r"\bcancel\w*\b.*?\b(refund|money|back)\b|\b(refund|money|back)\b.*?\bcancel\w*\b", lower_text, re.DOTALL):
        return {"intent": "escalate", "customer_email": customer_email}

    # If user provides an email directly in response to an email prompt, route straight to tool
    latest_email = _extract_email_from_text(user_text)
    if latest_email:
        customer_email = latest_email
        if len(user_text.split()) <= 4:
            return {"intent": "tool", "customer_email": customer_email}

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

    return {"intent": intent, "customer_email": customer_email}


def rag_node(state: AgentState) -> Dict[str, Any]:
    """
    Retrieve knowledge base documents and generate a grounded answer with Haiku.
    If no documents meet the min_confidence threshold, redirect to off_topic.
    """
    messages = state.get("messages", [])
    user_text = _get_latest_user_text(messages)
    customer_email = state.get("customer_email")

    retrieved = retrieve(query=user_text, k=3, min_confidence=1.3)

    if not retrieved:
        # Fall back to off_topic redirect if no relevant knowledge found
        return {
            "intent": "off_topic",
            "customer_email": customer_email,
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
        "customer_email": customer_email,
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
    user_text = _get_latest_user_text(messages)
    customer_email = state.get("customer_email") or _extract_recent_email(messages)

    # Pre-check: If no customer email is set and the request needs a lookup, ask for email without calling tools
    if not customer_email and _needs_customer_lookup(user_text):
        return {
            "intent": "tool",
            "customer_email": None,
            "tool_result": None,
            "messages": [
                AIMessage(
                    content="To look up your order status or manage your subscription, please provide the email address associated with your account."
                )
            ],
        }

    # Set scoped session email for mock_api lookups
    mock_api.set_session_email(customer_email)

    tool_map = {t.name: t for t in AURELIO_TOOLS}

    model = get_model(temperature=0)
    model_with_tools = model.bind_tools(AURELIO_TOOLS)

    tool_call_response = model_with_tools.invoke(messages)

    # Check if a tool call was issued
    if not tool_call_response.tool_calls:
        return {
            "intent": "tool",
            "customer_email": customer_email,
            "tool_result": None,
            "messages": [tool_call_response],
        }

    # Execute every tool call and construct a ToolMessage for EACH tool_use_id
    tool_messages = []
    tool_outputs = []

    for tool_call in tool_call_response.tool_calls:
        tool_name = tool_call["name"]
        tool_args = dict(tool_call["args"])
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
            "warmly and clearly to the customer. "
            "If an order or subscription lookup returns an unauthorized error or 'I don't have access to that order', "
            "explain politely that you don't have access to that order under their account email. "
            "Never confirm or deny whether the order exists, and never reveal whose order it is. "
            "If any tool output contains an error (such as a service timeout), apologize graciously and suggest retrying in a moment "
            "or offering to connect them with a human specialist."
        )
    )

    final_conversation = [system_tool_prompt] + list(messages) + [tool_call_response] + tool_messages
    final_response = model.invoke(final_conversation)

    primary_result = tool_outputs[0] if len(tool_outputs) == 1 else {"results": tool_outputs}

    return {
        "intent": "tool",
        "customer_email": customer_email,
        "tool_result": primary_result,
        "messages": [tool_call_response] + tool_messages + [final_response],
    }


def escalation_node(state: AgentState) -> Dict[str, Any]:
    """Return fixed, non-LLM escalation response."""
    return {
        "intent": "escalate",
        "customer_email": state.get("customer_email"),
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
        "customer_email": state.get("customer_email"),
        "retrieved_context": [],
        "messages": [AIMessage(content=OFF_TOPIC_MESSAGE)],
    }
