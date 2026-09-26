import sys
from typing import Any, Dict
from langchain_core.messages import HumanMessage

# Ensure utf-8 stdout on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.agent.graph import graph
from app.tools import mock_api


def print_state_summary(test_num: int, title: str, state: Dict[str, Any]):
    print(f"\n{'=' * 80}")
    print(f"TEST {test_num}: {title}")
    print(f"{'=' * 80}")
    print(f"Intent: {state.get('intent')}")
    print(f"Retrieved Context Count: {len(state.get('retrieved_context', []) or [])}")
    print(f"Tool Result: {state.get('tool_result')}")
    
    messages = state.get("messages", [])
    print(f"Total Messages in Thread: {len(messages)}")
    if messages:
        last_msg = messages[-1]
        print(f"Latest Assistant Response:\n{last_msg.content}")


def run_all_tests():
    print("STARTING LANGGRAPH AGENT TEST SUITE (6 SCENARIOS)")

    # -------------------------------------------------------------
    # 1. RAG question
    # -------------------------------------------------------------
    thread_1 = {"configurable": {"thread_id": "session-rag-001"}}
    state_1 = graph.invoke(
        {"messages": [HumanMessage(content="What are the tasting notes and origin of the Colombia Huila roast?")]},
        config=thread_1,
    )
    print_state_summary(1, "RAG Question", state_1)

    # -------------------------------------------------------------
    # 2. Tool-call question
    # -------------------------------------------------------------
    thread_2 = {"configurable": {"thread_id": "session-tool-002"}}
    state_2 = graph.invoke(
        {"messages": [HumanMessage(content="Can you please check the tracking status of my order ORD-101?")]},
        config=thread_2,
    )
    print_state_summary(2, "Tool Call Question", state_2)

    # -------------------------------------------------------------
    # 3. Refund request (Hardcoded escalation)
    # -------------------------------------------------------------
    thread_3 = {"configurable": {"thread_id": "session-escalate-003"}}
    state_3 = graph.invoke(
        {"messages": [HumanMessage(content="My coffee package arrived damaged and I would like a refund.")]},
        config=thread_3,
    )
    print_state_summary(3, "Refund Request (Escalation)", state_3)

    # -------------------------------------------------------------
    # 4. Off-topic request
    # -------------------------------------------------------------
    thread_4 = {"configurable": {"thread_id": "session-offtopic-004"}}
    state_4 = graph.invoke(
        {"messages": [HumanMessage(content="Write me a Python script to calculate Fibonacci numbers.")]},
        config=thread_4,
    )
    print_state_summary(4, "Off-Topic Request", state_4)

    # -------------------------------------------------------------
    # 5. Multi-turn conversation testing memory
    # -------------------------------------------------------------
    thread_5 = {"configurable": {"thread_id": "session-memory-005"}}
    # Turn 1
    state_5_t1 = graph.invoke(
        {"messages": [HumanMessage(content="I am looking for your lightest roast coffee. What do you recommend?")]},
        config=thread_5,
    )
    # Turn 2 referencing previous turn
    state_5_t2 = graph.invoke(
        {"messages": [HumanMessage(content="What brewing method and ratio work best for that specific roast?")]},
        config=thread_5,
    )
    print_state_summary(5, "Multi-Turn Memory Test (Turn 2)", state_5_t2)

    # -------------------------------------------------------------
    # 6. Tool call that hits simulated failure case
    # -------------------------------------------------------------
    # Force failure for this specific run
    orig_failure_fn = mock_api._should_simulate_failure
    mock_api._should_simulate_failure = lambda _force=False: True
    try:
        thread_6 = {"configurable": {"thread_id": "session-fail-006"}}
        state_6 = graph.invoke(
            {"messages": [HumanMessage(content="Could you check my subscription status for sarah@example.com?")]},
            config=thread_6,
        )
        print_state_summary(6, "Tool Call with Simulated Service Timeout", state_6)
    finally:
        mock_api._should_simulate_failure = orig_failure_fn

    print(f"\n{'=' * 80}")
    print("ALL 6 TESTS FINISHED SUCCESSFULLY")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    run_all_tests()
