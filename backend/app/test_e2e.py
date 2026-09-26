import asyncio
import json
import sys
import httpx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


async def test_endpoint(session_id: str, message: str, scenario_name: str):
    print(f"\n{'=' * 80}")
    print(f"SCENARIO: {scenario_name}")
    print(f"User ({session_id}): \"{message}\"")
    print(f"{'=' * 80}")

    tokens = []
    events = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST",
            "http://127.0.0.1:8000/chat/stream",
            json={"session_id": session_id, "message": message},
        ) as response:
            current_event = None
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    current_event = None
                    continue
                if line.startswith("event:"):
                    current_event = line.replace("event:", "").strip()
                    events.append(current_event)
                    print(f"  [EVENT]: {current_event}")
                elif line.startswith("data:"):
                    data_str = line.replace("data:", "").strip()
                    try:
                        payload = json.loads(data_str)
                    except Exception:
                        payload = data_str

                    if current_event == "tool_call":
                        print(f"  [TOOL_CALL DATA]: {payload}")
                    elif current_event == "done":
                        print(f"  [DONE DATA]: {payload}")
                    elif isinstance(payload, dict) and "token" in payload:
                        token = payload["token"]
                        tokens.append(token)
                        print(token, end="", flush=True)

    print()
    full_text = "".join(tokens)
    print(f"\n[Summary]: Received {len(events)} events, {len(tokens)} token chunks.")
    print(f"[Full Response]:\n{full_text}")
    return events, full_text


async def main():
    print("RUNNING END-TO-END VERIFICATION AGAINST LIVE LOCAL BACKEND (PORT 8000)")

    # 1. RAG question
    await test_endpoint(
        "e2e-rag-session",
        "What are the tasting notes of the Colombia Huila roast?",
        "1. RAG Question",
    )

    # 2. Tool-call question
    await test_endpoint(
        "e2e-tool-session",
        "Can you check the tracking status of order ORD-101?",
        "2. Tool-Call Question",
    )

    # 3. Escalation question
    await test_endpoint(
        "e2e-escalate-session",
        "My bag arrived completely damaged and I want a refund.",
        "3. Escalation Request",
    )


if __name__ == "__main__":
    asyncio.run(main())
