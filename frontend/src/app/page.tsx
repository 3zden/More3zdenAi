"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { sendMessage, Message, Source } from "@/lib/api";

const SUGGESTED_QUESTIONS = [
  "What technologies does Azzeddine work with?",
  "Tell me about the More3zdenAI project",
  "What services does Azzeddine offer?",
  "Is Azzeddine available for hire?",
  "What is Azzeddine's experience?",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm More3zdenAI 👋 Ask me anything about Azzeddine's skills, projects, experience, or how to get in touch.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sessionId] = useState(uuidv4());
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(
    async (question?: string) => {
      const q = (question || input).trim();
      if (!q || loading) return;

      const userMsg: Message = { id: uuidv4(), role: "user", content: q };
      const placeholderId = uuidv4();
      const placeholder: Message = {
        id: placeholderId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, placeholder]);
      setInput("");
      setLoading(true);

      try {
        const res = await sendMessage(q, sessionId);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === placeholderId
              ? {
                  ...m,
                  content: res.answer,
                  sources: res.sources,
                  cached: res.cached,
                  latency_ms: res.latency_ms,
                  isStreaming: false,
                }
              : m
          )
        );
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === placeholderId
              ? {
                  ...m,
                  content: "Sorry, something went wrong. Please try again.",
                  isStreaming: false,
                }
              : m
          )
        );
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    },
    [input, loading, sessionId]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-sm font-bold">
          M
        </div>
        <div>
          <h1 className="font-semibold text-white">More3zdenAI</h1>
          <p className="text-xs text-gray-400">Powered by Ollama · RAG · FAISS</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs text-gray-400">Online</span>
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto px-4 py-6 max-w-3xl mx-auto w-full">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Suggested questions (only at start) */}
        {messages.length === 1 && (
          <div className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className="text-left px-4 py-3 rounded-xl border border-gray-700 bg-gray-900 hover:border-violet-500 hover:bg-gray-800 transition text-sm text-gray-300"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      {/* Input */}
      <footer className="border-t border-gray-800 px-4 py-4">
        <div className="max-w-3xl mx-auto flex gap-3 items-end">
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me about Morad's skills, projects, experience..."
            className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-500 resize-none focus:outline-none focus:border-violet-500 transition"
            disabled={loading}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="px-4 py-3 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed transition text-white font-medium text-sm"
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
        <p className="text-center text-xs text-gray-600 mt-2">
          Answers are grounded in Azzeddine's actual portfolio data via RAG
        </p>
      </footer>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`mb-6 flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] ${isUser ? "order-2" : "order-1"}`}>
        {/* Avatar */}
        {!isUser && (
          <div className="flex items-center gap-2 mb-1">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-xs font-bold">
              M
            </div>
            <span className="text-xs text-gray-500">More3zdenAI</span>
            {message.cached && (
              <span className="text-xs text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                cached
              </span>
            )}
            {message.latency_ms && (
              <span className="text-xs text-gray-600">{message.latency_ms}ms</span>
            )}
          </div>
        )}

        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
            isUser
              ? "bg-violet-600 text-white rounded-tr-sm"
              : "bg-gray-800 text-gray-100 rounded-tl-sm"
          }`}
        >
          {message.isStreaming ? (
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "300ms" }} />
            </span>
          ) : (
            message.content
          )}
        </div>

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <SourcesList sources={message.sources} />
        )}
      </div>
    </div>
  );
}

function SourcesList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-gray-500 hover:text-gray-300 transition flex items-center gap-1"
      >
        <span>{open ? "▲" : "▼"}</span>
        {sources.length} source{sources.length !== 1 ? "s" : ""}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {sources.map((s, i) => (
            <div key={i} className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs">
              <div className="flex items-center justify-between mb-1">
                <span className="text-violet-400 font-medium">{s.section}</span>
                <span className="text-gray-500">score: {s.score.toFixed(2)}</span>
              </div>
              <p className="text-gray-400 leading-relaxed">{s.preview}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
