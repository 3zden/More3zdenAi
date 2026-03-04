"""
Ollama LLM Client
Handles prompt engineering, context injection, response caching,
and streaming support for local Ollama models.
"""
import hashlib
import json
import os
import time
from typing import Generator, List, Optional

import requests

# ── Configuration ──────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))

# ── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are More3zdenAI, the personal AI assistant for Morad's developer portfolio.
Your role is to help visitors learn about Morad's skills, projects, experience, and services.

Guidelines:
- Be friendly, concise, and professional.
- Answer only based on the provided context. If the answer is not in the context, say so honestly.
- Keep responses under 200 words unless a detailed explanation is explicitly requested.
- Use bullet points for lists of skills, technologies, or features.
- Always refer to Morad in the third person (e.g., "Morad has experience with...").
- Do NOT make up projects, skills, or experiences not mentioned in the context.
- If asked about availability or hiring, be encouraging and direct visitors to the contact section.
"""

RAG_PROMPT_TEMPLATE = """Use the following context from Morad's portfolio to answer the question.

CONTEXT:
{context}

QUESTION: {question}

Answer clearly and concisely based only on the context above:"""


class OllamaClient:
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._cache: dict = {}  # In-memory cache (Redis used in production)

    # ── Cache helpers ─────────────────────────────────────────────────────────
    def _cache_key(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def _from_cache(self, key: str) -> Optional[str]:
        entry = self._cache.get(key)
        if entry and (time.time() - entry["ts"] < 3600):  # 1h TTL
            return entry["value"]
        return None

    def _to_cache(self, key: str, value: str) -> None:
        self._cache[key] = {"value": value, "ts": time.time()}

    # ── Build RAG prompt ──────────────────────────────────────────────────────
    def build_prompt(self, question: str, context_chunks: List[str]) -> str:
        context = "\n\n---\n\n".join(context_chunks)
        return RAG_PROMPT_TEMPLATE.format(context=context, question=question)

    # ── Health check ──────────────────────────────────────────────────────────
    def is_healthy(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    # ── Non-streaming inference ───────────────────────────────────────────────
    def generate(
        self,
        question: str,
        context_chunks: List[str],
        use_cache: bool = True,
    ) -> dict:
        prompt = self.build_prompt(question, context_chunks)
        cache_key = self._cache_key(f"{self.model}:{prompt}")

        if use_cache:
            cached = self._from_cache(cache_key)
            if cached:
                return {"response": cached, "cached": True, "model": self.model}

        start = time.time()
        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,      # Lower = more factual
                "top_p": 0.9,
                "num_predict": 512,      # Max tokens
            },
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            response_text = data.get("response", "").strip()
            latency = round(time.time() - start, 3)

            if use_cache:
                self._to_cache(cache_key, response_text)

            return {
                "response": response_text,
                "cached": False,
                "model": self.model,
                "latency_s": latency,
            }

        except requests.exceptions.Timeout:
            return {"error": "LLM timeout. Please try again.", "model": self.model}
        except requests.exceptions.ConnectionError:
            return {"error": "Cannot connect to Ollama. Is it running?", "model": self.model}
        except Exception as e:
            return {"error": str(e), "model": self.model}

    # ── Streaming inference ───────────────────────────────────────────────────
    def stream(
        self,
        question: str,
        context_chunks: List[str],
    ) -> Generator[str, None, None]:
        prompt = self.build_prompt(question, context_chunks)
        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 512},
        }

        try:
            with requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True,
                timeout=OLLAMA_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
        except Exception as e:
            yield f"\n[Error: {str(e)}]"


# ── Singleton ──────────────────────────────────────────────────────────────────
_ollama_client: OllamaClient | None = None


def get_ollama_client() -> OllamaClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client
