from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Shared state for the Aurelio Coffee Co. customer support agent.
    
    Attributes:
        messages: List of conversation messages with add_messages reducer.
        intent: Intent classified by router ('rag', 'tool', 'escalate', 'off_topic').
        retrieved_context: Knowledge base chunks retrieved for RAG grounding.
        tool_result: Execution result from mock API tool call or None.
    """
    messages: Annotated[list, add_messages]
    intent: str
    retrieved_context: list
    tool_result: Optional[dict]
    customer_email: Optional[str]
