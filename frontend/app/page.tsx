"use client";

import React, { useEffect, useRef, useState } from "react";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  isEscalated?: boolean;
}

const TOOL_DESCRIPTIONS: Record<string, string> = {
  check_order_status: "Checking order status and tracking...",
  check_subscription_status: "Accessing subscription account details...",
  pause_subscription: "Updating subscription schedule...",
  get_plan_pricing: "Looking up subscription tier pricing...",
};

const SUGGESTED_PROMPTS = [
  "What is the Colombia Huila roast?",
  "How do I brew pour-over coffee?",
  "Check status of order ORD-101",
  "Can I pause my subscription?",
];

// Helper to render basic markdown formatting (bold, headers, bullets, linebreaks)
function renderMarkdown(text: string) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    // Headers
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h4 key={index} className="text-sm font-bold text-stone-900 mt-2 mb-1">
          {formatInline(trimmed.slice(4))}
        </h4>
      );
      return;
    }
    if (trimmed.startsWith("## ")) {
      elements.push(
        <h3 key={index} className="text-base font-bold text-stone-900 mt-3 mb-1">
          {formatInline(trimmed.slice(3))}
        </h3>
      );
      return;
    }
    if (trimmed.startsWith("# ")) {
      elements.push(
        <h2 key={index} className="text-lg font-bold text-stone-900 mt-3 mb-1.5">
          {formatInline(trimmed.slice(2))}
        </h2>
      );
      return;
    }

    // Unordered lists (- or *)
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      elements.push(
        <div key={index} className="flex items-start space-x-2 my-0.5 pl-2">
          <span className="text-amber-800 font-bold leading-relaxed">•</span>
          <span className="flex-1">{formatInline(trimmed.slice(2))}</span>
        </div>
      );
      return;
    }

    // Ordered lists (e.g. 1. , 2. )
    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (orderedMatch) {
      elements.push(
        <div key={index} className="flex items-start space-x-2 my-0.5 pl-2">
          <span className="text-amber-900/80 font-medium text-xs leading-relaxed mt-0.5">
            {orderedMatch[1]}.
          </span>
          <span className="flex-1">{formatInline(orderedMatch[2])}</span>
        </div>
      );
      return;
    }

    // Blank line
    if (!trimmed) {
      elements.push(<div key={index} className="h-2" />);
      return;
    }

    // Regular paragraph
    elements.push(
      <p key={index} className="leading-relaxed my-0.5">
        {formatInline(line)}
      </p>
    );
  });

  return elements;
}

// Inline parser for **bold** and `code`
function formatInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-stone-900">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={i}
          className="rounded bg-stone-100 px-1 py-0.5 text-xs font-mono text-amber-900"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeToolCall, setActiveToolCall] = useState<string | null>(null);
  const [limitReached, setLimitReached] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 1. Initialize or load session_id from sessionStorage (per tab)
  useEffect(() => {
    let sid = sessionStorage.getItem("aurelio_chat_session_id");
    if (!sid) {
      sid = crypto.randomUUID();
      sessionStorage.setItem("aurelio_chat_session_id", sid);
    }
    setSessionId(sid);
  }, []);

  // 2. Auto-scroll to bottom whenever messages or tool calls update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeToolCall, isStreaming]);

  // Adjust textarea height dynamically
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        140
      )}px`;
    }
  };

  // Submit message
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputValue).trim();
    if (!text || isStreaming || limitReached) return;

    setInputValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);
    setActiveToolCall(null);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    try {
      const response = await fetch(`${apiUrl}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream, application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
        }),
      });

      // Handle non-stream JSON response (e.g. Rate limit or message limit reached)
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const data = await response.json();
        if (data.limit_reached) {
          setLimitReached(true);
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: "system",
              content:
                data.message ||
                "This demo session has a message limit — refresh the page to start a new one.",
            },
          ]);
        } else if (data.message) {
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: "system",
              content: data.message,
            },
          ]);
        }
        setIsStreaming(false);
        return;
      }

      if (!response.body) {
        throw new Error("No response body received from server.");
      }

      // Read SSE Stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const lines = part.split("\n");
          let eventType = "message";
          let dataStr = "";

          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.replace("event:", "").trim();
            } else if (line.startsWith("data:")) {
              dataStr = line.replace("data:", "").trim();
            }
          }

          if (!dataStr && eventType !== "done") continue;

          // 1. Tool call notification event
          if (eventType === "tool_call") {
            try {
              const payload = JSON.parse(dataStr);
              const toolName = payload.tool || "";
              setActiveToolCall(
                TOOL_DESCRIPTIONS[toolName] || `Consulting Aurelio backend (${toolName})...`
              );
            } catch {
              setActiveToolCall("Consulting Aurelio system...");
            }
          }
          // 2. Stream completion event
          else if (eventType === "done") {
            setIsStreaming(false);
            setActiveToolCall(null);
            try {
              const donePayload = JSON.parse(dataStr);
              if (donePayload.intent === "escalate") {
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  if (last && last.role === "assistant") {
                    return [
                      ...prev.slice(0, -1),
                      { ...last, isEscalated: true },
                    ];
                  }
                  return prev;
                });
              }
            } catch {
              // ignore parse errors
            }
          }
          // 3. Error event
          else if (eventType === "error") {
            setIsStreaming(false);
            setActiveToolCall(null);
            try {
              const errPayload = JSON.parse(dataStr);
              setMessages((prev) => [
                ...prev,
                {
                  id: crypto.randomUUID(),
                  role: "system",
                  content:
                    errPayload.message ||
                    "Something went wrong on our end — please try again.",
                },
              ]);
            } catch {
              setMessages((prev) => [
                ...prev,
                {
                  id: crypto.randomUUID(),
                  role: "system",
                  content: "Something went wrong on our end — please try again.",
                },
              ]);
            }
          }
          // 4. Token payload
          else {
            try {
              const payload = JSON.parse(dataStr);
              if (payload.token) {
                // Clear tool indicator as response text starts arriving
                setActiveToolCall(null);

                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  if (last && last.role === "assistant") {
                    const newContent = last.content + payload.token;
                    const isEscalated =
                      last.isEscalated ||
                      newContent.includes(
                        "connecting you with a support specialist"
                      );
                    return [
                      ...prev.slice(0, -1),
                      { ...last, content: newContent, isEscalated },
                    ];
                  } else {
                    const isEscalated = payload.token.includes(
                      "connecting you with a support specialist"
                    );
                    return [
                      ...prev,
                      {
                        id: crypto.randomUUID(),
                        role: "assistant",
                        content: payload.token,
                        isEscalated,
                      },
                    ];
                  }
                });
              }
            } catch {
              // Ignore non-json lines
            }
          }
        }
      }
    } catch (err) {
      console.error("Stream reader error:", err);
      setIsStreaming(false);
      setActiveToolCall(null);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "system",
          content:
            "Could not connect to Aurelio support server. Please make sure the backend is running.",
        },
      ]);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex h-screen flex-col bg-[#FDFBF7] text-stone-800 antialiased">
      {/* Brand Header */}
      <header className="border-b border-[#EAE3D9] bg-white/90 backdrop-blur-md px-4 py-3 sticky top-0 z-20 shadow-xs">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 rounded-full bg-[#2C1810] flex items-center justify-center text-amber-100 shadow-sm">
              {/* Coffee Cup Icon */}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-5 h-5"
              >
                <path d="M17 8h1a4 4 0 1 1 0 8h-1" />
                <path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4Z" />
                <line x1="6" y1="2" x2="6" y2="4" />
                <line x1="10" y1="2" x2="10" y2="4" />
                <line x1="14" y1="2" x2="14" y2="4" />
              </svg>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-base font-bold tracking-tight text-[#2C1810]">
                  Aurelio Coffee Co.
                </h1>
                <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 border border-emerald-200">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 mr-1 animate-pulse" />
                  Live Support
                </span>
              </div>
              <p className="text-xs text-stone-500 font-normal">
                Ask me about our coffee, your order, or your subscription
              </p>
            </div>
          </div>

          <div className="text-right hidden sm:block">
            <span className="text-[11px] text-stone-400 font-mono">
              Session: {sessionId.slice(0, 8)}...
            </span>
          </div>
        </div>
      </header>

      {/* Chat Messages Area */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-5">
          {/* Welcome Screen when conversation is empty */}
          {messages.length === 0 && (
            <div className="my-8 text-center px-4">
              <div className="mx-auto mb-4 h-12 w-12 rounded-2xl bg-[#F4EFEA] flex items-center justify-center text-amber-900 border border-[#E5DDD2]">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="1.75"
                    d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                  />
                </svg>
              </div>
              <h2 className="text-lg font-semibold text-[#2C1810]">
                Welcome to Aurelio Coffee
              </h2>
              <p className="mt-1 text-sm text-stone-600 max-w-md mx-auto">
                I can help you find single-origin beans, guide your brew ratios,
                track packages, or manage your recurring deliveries.
              </p>

              {/* Starter suggestions */}
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {SUGGESTED_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(prompt)}
                    className="rounded-full border border-[#E7DFD5] bg-white px-3.5 py-1.5 text-xs text-stone-700 shadow-2xs hover:bg-[#F4EFEA] hover:border-amber-300 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Message History */}
          {messages.map((msg) => {
            if (msg.role === "user") {
              return (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[85%] sm:max-w-[75%] rounded-2xl rounded-tr-xs bg-[#2C1810] px-4 py-2.5 text-sm text-white shadow-xs">
                    <p className="leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </p>
                  </div>
                </div>
              );
            }

            if (msg.role === "system") {
              return (
                <div key={msg.id} className="flex justify-center my-3">
                  <div className="rounded-xl border border-amber-200/80 bg-amber-50/70 px-4 py-2 text-xs text-amber-900 max-w-md text-center shadow-2xs">
                    {msg.content}
                  </div>
                </div>
              );
            }

            // Escalation Card Style
            if (msg.isEscalated) {
              return (
                <div key={msg.id} className="flex justify-start">
                  <div className="max-w-[88%] sm:max-w-[78%] rounded-2xl rounded-tl-xs border border-amber-300 bg-amber-50/90 p-4 shadow-sm text-stone-900">
                    <div className="flex items-center space-x-2 pb-2 mb-2 border-b border-amber-200">
                      <div className="h-6 w-6 rounded-full bg-amber-500/20 text-amber-900 flex items-center justify-center">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="h-3.5 w-3.5"
                          viewBox="0 0 20 20"
                          fill="currentColor"
                        >
                          <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 4V3z" />
                        </svg>
                      </div>
                      <span className="text-xs font-semibold tracking-wide text-amber-900 uppercase">
                        Connecting to Support Specialist
                      </span>
                    </div>
                    <div className="text-sm leading-relaxed text-amber-950 font-medium">
                      {msg.content}
                    </div>
                    <p className="mt-2 text-[11px] text-amber-800/80">
                      Our human concierge team typically responds within 1–2 business days.
                    </p>
                  </div>
                </div>
              );
            }

            // Standard Assistant Bubble
            return (
              <div key={msg.id} className="flex justify-start">
                <div className="max-w-[88%] sm:max-w-[78%] rounded-2xl rounded-tl-xs border border-[#E7E0D6] bg-white px-4 py-3 text-sm text-stone-800 shadow-2xs">
                  <div className="text-sm">{renderMarkdown(msg.content)}</div>
                </div>
              </div>
            );
          })}

          {/* Active Tool Call Indicator */}
          {activeToolCall && (
            <div className="flex justify-start animate-fade-in">
              <div className="inline-flex items-center space-x-2 rounded-full border border-amber-200 bg-amber-50/80 px-3 py-1 text-xs text-amber-900 shadow-2xs">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-600"></span>
                </span>
                <span className="font-medium">{activeToolCall}</span>
              </div>
            </div>
          )}

          {/* Loading Dot Animation while waiting for first token if no tool called */}
          {isStreaming && !activeToolCall && messages[messages.length - 1]?.role === "user" && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-tl-xs border border-[#E7E0D6] bg-white px-4 py-3 shadow-2xs">
                <div className="flex items-center space-x-1.5">
                  <div className="h-2 w-2 rounded-full bg-stone-400 animate-bounce" />
                  <div
                    className="h-2 w-2 rounded-full bg-stone-400 animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <div
                    className="h-2 w-2 rounded-full bg-stone-400 animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <footer className="border-t border-[#EAE3D9] bg-white/95 backdrop-blur-md p-4 sticky bottom-0 z-20">
        <div className="max-w-3xl mx-auto">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-end space-x-2 rounded-2xl border border-[#DCD3C6] bg-white p-1.5 focus-within:border-[#2C1810] focus-within:ring-1 focus-within:ring-[#2C1810] transition-all shadow-xs"
          >
            <textarea
              ref={textareaRef}
              rows={1}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              disabled={isStreaming || limitReached}
              placeholder={
                limitReached
                  ? "Session limit reached — refresh to start over"
                  : "Ask about coffee, order tracking, or brewing..."
              }
              className="flex-1 max-h-32 resize-none bg-transparent px-3 py-1.5 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-hidden disabled:opacity-50 disabled:cursor-not-allowed leading-relaxed"
            />
            <button
              type="submit"
              disabled={isStreaming || !inputValue.trim() || limitReached}
              className="rounded-xl bg-[#2C1810] p-2 text-white hover:bg-[#402318] disabled:opacity-30 disabled:hover:bg-[#2C1810] transition-colors shrink-0"
              aria-label="Send message"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-4 h-4"
              >
                <path d="M3.105 2.289a.75.75 0 0 0-.826.95l1.414 4.925A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.086l-1.414 4.926a.75.75 0 0 0 .826.95 28.896 28.896 0 0 0 15.293-7.154.75.75 0 0 0 0-1.115A28.897 28.897 0 0 0 3.105 2.289Z" />
              </svg>
            </button>
          </form>

          <div className="mt-2 flex items-center justify-between text-[11px] text-stone-400 px-1">
            <span>Press Enter to send, Shift+Enter for new line</span>
            <span>Aurelio Support Agent &bull; Powered by LangGraph & Haiku</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
