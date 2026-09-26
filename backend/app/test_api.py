import asyncio
import json
import sys
import httpx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.main import app


async def send_chat_message(client: httpx.AsyncClient, session_id: str, message: str):
    print(f"\n---> User ({session_id}): \"{message}\"")
    
    events_received = []
    tokens = []
    
    async with client.stream(
        "POST",
        "/chat/stream",
        json={"session_id": session_id, "message": message},
        timeout=30.0,
    ) as response:
        content_type = response.headers.get("content-type", "")
        
        # Check if non-streamed JSON was returned (e.g. limit reached)
        if "application/json" in content_type:
            raw_body = await response.aread()
            data = json.loads(raw_body)
            print(f"[JSON Response]: {data}")
            return data

        # Process SSE Stream
        current_event = None
        async for line in response.aiter_lines():
            line = line.strip()
            if not line:
                current_event = None
                continue

            if line.startswith("event:"):
                current_event = line.replace("event:", "").strip()
                events_received.append(f"event:{current_event}")
            elif line.startswith("data:"):
                data_str = line.replace("data:", "").strip()
                try:
                    payload = json.loads(data_str)
                except Exception:
                    payload = data_str

                if current_event == "tool_call":
                    tool_name = payload.get("tool") if isinstance(payload, dict) else payload
                    print(f"  [SSE Tool Call]: {tool_name}")
                elif current_event == "done":
                    print("  [SSE Event]: done")
                elif current_event == "error":
                    print(f"  [SSE Error]: {payload}")
                else:
                    if isinstance(payload, dict) and "token" in payload:
                        token = payload["token"]
                        tokens.append(token)
                        print(token, end="", flush=True)

    print()
    full_response = "".join(tokens)
    return full_response


async def run_api_tests():
    print("=" * 80)
    print("AURELIO COFFEE CO. — FASTAPI BACKEND TEST SUITE (/chat/stream)")
    print("=" * 80)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check test
        health_res = await client.get("/health")
        print(f"1. GET /health -> Status: {health_res.status_code}, Body: {health_res.json()}")
        assert health_res.status_code == 200
        assert health_res.json() == {"status": "ok"}

        # 2. Multi-turn conversation on single session_id testing memory
        session_id = "test-session-multi-turn-001"
        print(f"\n2. Testing Multi-Turn Session Persistence on thread: {session_id}")

        # Turn 1: Inquire about Sumatra Mandheling
        print("\n--- Turn 1 ---")
        reply_1 = await send_chat_message(
            client,
            session_id,
            "Tell me about the Sumatra Mandheling coffee.",
        )

        # Turn 2: Follow-up referencing earlier turn
        print("\n--- Turn 2 (referencing Turn 1) ---")
        reply_2 = await send_chat_message(
            client,
            session_id,
            "What brewing method do you recommend for that roast?",
        )

        # 3. Tool call test with SSE event
        tool_session = "test-session-tool-002"
        print(f"\n3. Testing Tool Call SSE Event on thread: {tool_session}")
        await send_chat_message(
            client,
            tool_session,
            "Can you look up order ORD-101 for me?",
        )

        # 4. Session message limit enforcement test
        print()
        limit_session = "test-session-limit-003"
        print(f"\n4. Testing Session Message Limit Enforcement on thread: {limit_session}")
        from app.core.rate_limit import session_message_counts
        from app.core.config import settings
        session_message_counts[limit_session] = settings.MAX_MESSAGES_PER_SESSION
        limit_reply = await send_chat_message(
            client,
            limit_session,
            "Hello, is this allowed?",
        )
        assert isinstance(limit_reply, dict)
        assert limit_reply.get("limit_reached") is True
        print(f"  [Verified]: Session limit correctly rejected with JSON response: {limit_reply}")

    print("\n" + "=" * 80)
    print("ALL API TESTS COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_api_tests())
