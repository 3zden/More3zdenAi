const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Source {
  section: string;
  source: string;
  score: number;
  preview: string;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  session_id: string;
  cached: boolean;
  latency_ms: number;
  model: string;
  error?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  cached?: boolean;
  latency_ms?: number;
  isStreaming?: boolean;
}

export async function sendMessage(
  question: string,
  sessionId?: string
): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/api/chat/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: sessionId }),
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

export async function checkHealth() {
  const res = await fetch(`${API_URL}/api/health/`, { cache: "no-store" });
  return res.json();
}

export function streamMessage(
  question: string,
  onToken: (token: string) => void,
  onSources: (sources: Source[]) => void,
  onDone: () => void,
  onError: (err: string) => void
): EventSource {
  const url = `${API_URL}/api/chat/stream/?question=${encodeURIComponent(question)}`;
  const es = new EventSource(url);

  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.type === "sources") onSources(data.sources);
      else if (data.type === "token") onToken(data.token);
      else if (data.type === "done") {
        onDone();
        es.close();
      }
    } catch {}
  };

  es.onerror = () => {
    onError("Streaming connection lost.");
    es.close();
  };

  return es;
}
