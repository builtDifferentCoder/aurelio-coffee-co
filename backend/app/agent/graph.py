from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    escalation_node,
    off_topic_node,
    rag_node,
    router_node,
    tool_node,
)
from app.agent.state import AgentState


def route_intent(state: AgentState) -> str:
    """Route from router_node based on state['intent']."""
    intent = state.get("intent", "off_topic")
    if intent == "rag":
        return "rag_node"
    elif intent == "tool":
        return "tool_node"
    elif intent == "escalate":
        return "escalation_node"
    return "off_topic_node"


# Initialize StateGraph with AgentState schema
workflow = StateGraph(AgentState)

# Add all 5 nodes
workflow.add_node("router_node", router_node)
workflow.add_node("rag_node", rag_node)
workflow.add_node("tool_node", tool_node)
workflow.add_node("escalation_node", escalation_node)
workflow.add_node("off_topic_node", off_topic_node)

# Flow: START -> router_node
workflow.add_edge(START, "router_node")

# Conditional edge routing on state["intent"]
workflow.add_conditional_edges(
    "router_node",
    route_intent,
    {
        "rag_node": "rag_node",
        "tool_node": "tool_node",
        "escalation_node": "escalation_node",
        "off_topic_node": "off_topic_node",
    },
)

# Terminal edges: each specialized node completes at END
workflow.add_edge("rag_node", END)
workflow.add_edge("tool_node", END)
workflow.add_edge("escalation_node", END)
workflow.add_edge("off_topic_node", END)

# In-memory checkpointer for per-session thread persistence
checkpointer = MemorySaver()

# Compiled LangGraph agent
graph = workflow.compile(checkpointer=checkpointer)
