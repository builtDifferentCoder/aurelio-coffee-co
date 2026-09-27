import json
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.agent.graph import graph
from app.core.config import settings
from app.core.rate_limit import check_session_limit, limiter

logger = logging.getLogger("aurelio.api")

app = FastAPI(
    title="Aurelio Coffee Co. AI Agent API",
    description="Backend API for Aurelio Coffee Co. customer support and sales agent",
    version="0.1.0",
)

# Configure SlowAPI limiter on app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Client-generated unique session ID / thread ID")
    message: str = Field(..., description="Customer message")


async def event_generator(session_id: str, message: str) -> AsyncGenerator[str, None]:
    """
    Generate Server-Sent Events (SSE) from the LangGraph agent invocation.
    - Yields `event: tool_call` when a tool starts.
    - Yields `data: {"token": "..."}` for streamed tokens.
    - Yields `event: done` on completion.
    - Catches unhandled exceptions and yields `event: error`.
    """
    config = {"configurable": {"thread_id": session_id}}
    input_data = {"messages": [HumanMessage(content=message)]}
    tokens_streamed = 0
    final_intent = "rag"

    try:
        async for event in graph.astream_events(input_data, config=config, version="v2"):
            event_type = event.get("event")
            metadata = event.get("metadata", {})
            node_name = metadata.get("langgraph_node")

            # Capture node output intent
            if event_type == "on_chain_end":
                output_data = event.get("data", {}).get("output")
                if isinstance(output_data, dict) and "intent" in output_data:
                    final_intent = output_data["intent"]

            # 1. Distinct SSE event when a tool is called
            if event_type == "on_tool_start":
                tool_name = event.get("name", "tool")
                payload = json.dumps({"tool": tool_name})
                yield f"event: tool_call\ndata: {payload}\n\n"

            # 2. Token chunks from LLM in response nodes (rag_node, tool_node)
            elif event_type == "on_chat_model_stream" and node_name in ("rag_node", "tool_node"):
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    if isinstance(chunk.content, str) and chunk.content:
                        payload = json.dumps({"token": chunk.content})
                        tokens_streamed += 1
                        yield f"data: {payload}\n\n"
                    elif isinstance(chunk.content, list):
                        for part in chunk.content:
                            if isinstance(part, str) and part:
                                payload = json.dumps({"token": part})
                                tokens_streamed += 1
                                yield f"data: {payload}\n\n"
                            elif isinstance(part, dict) and part.get("text"):
                                payload = json.dumps({"token": part["text"]})
                                tokens_streamed += 1
                                yield f"data: {payload}\n\n"

            # 3. Deterministic node responses (escalation_node, off_topic_node, rag fallback, or tool pre-check)
            elif event_type == "on_chain_end" and event.get("name") in (
                "escalation_node",
                "off_topic_node",
                "rag_node",
                "tool_node",
            ):
                if tokens_streamed == 0:
                    node_output = event.get("data", {}).get("output", {})
                    output_messages = node_output.get("messages", []) if isinstance(node_output, dict) else []
                    if output_messages:
                        last_content = output_messages[-1].content
                        if last_content:
                            payload = json.dumps({"token": last_content})
                            tokens_streamed += 1
                            yield f"data: {payload}\n\n"

        # On successful completion, send final SSE event: "done" with final intent
        done_payload = json.dumps({"intent": final_intent})
        yield f"event: done\ndata: {done_payload}\n\n"

    except Exception as exc:
        logger.exception(f"Unhandled error during chat stream for session '{session_id}': {exc}")
        error_payload = json.dumps({
            "message": "Something went wrong on our end — please try again."
        })
        yield f"event: error\ndata: {error_payload}\n\n"


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/chat/stream")
@limiter.limit(f"{settings.RATE_LIMIT_PER_IP_DAILY}/day")
async def chat_stream(request: Request, body: ChatRequest):
    """
    Server-Sent Events (SSE) chat endpoint.
    Enforces per-session message limits before graph invocation.
    """
    # Check per-session limit before invoking the graph
    allowed, _ = check_session_limit(body.session_id)
    if not allowed:
        return JSONResponse(
            status_code=200,
            content={
                "limit_reached": True,
                "message": "This demo session has a message limit — refresh the page to start a new one.",
            },
        )

    return StreamingResponse(
        event_generator(body.session_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
