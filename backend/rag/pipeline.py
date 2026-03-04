"""
RAG Pipeline Orchestrator
Ties together: FAISS retrieval → context building → Ollama generation.
This is the single entry point used by Django views.
"""
import os
from dataclasses import dataclass
from typing import Generator, List, Optional

from .llm_client import OllamaClient, get_ollama_client
from .vector_store import FAISSVectorStore, get_vector_store

# ── Configuration ──────────────────────────────────────────────────────────────
TOP_K_RETRIEVAL = int(os.getenv("RAG_TOP_K", "5"))
MIN_RELEVANCE_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.3"))


@dataclass
class RAGResponse:
    answer: str
    sources: List[dict]
    cached: bool
    model: str
    latency_s: Optional[float] = None
    error: Optional[str] = None


class RAGPipeline:
    """
    Full RAG pipeline:
    1. Retrieve top-k relevant chunks from FAISS
    2. Filter by minimum relevance score
    3. Build context string
    4. Generate answer with Ollama
    """

    def __init__(
        self,
        vector_store: Optional[FAISSVectorStore] = None,
        llm_client: Optional[OllamaClient] = None,
    ):
        self._vector_store = vector_store
        self._llm_client = llm_client

    @property
    def vector_store(self) -> FAISSVectorStore:
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    @property
    def llm_client(self) -> OllamaClient:
        if self._llm_client is None:
            self._llm_client = get_ollama_client()
        return self._llm_client

    # ── Retrieve relevant context ─────────────────────────────────────────────
    def retrieve(self, question: str) -> tuple[List[str], List[dict]]:
        results = self.vector_store.search(question, top_k=TOP_K_RETRIEVAL)

        context_chunks = []
        sources = []

        for chunk, score in results:
            if score < MIN_RELEVANCE_SCORE:
                continue
            context_chunks.append(
                f"[{chunk.section}]\n{chunk.content}"
            )
            sources.append(
                {
                    "section": chunk.section,
                    "source": chunk.source,
                    "score": round(score, 4),
                    "preview": chunk.content[:120] + "...",
                }
            )

        return context_chunks, sources

    # ── Non-streaming RAG ─────────────────────────────────────────────────────
    def query(self, question: str, use_cache: bool = True) -> RAGResponse:
        context_chunks, sources = self.retrieve(question)

        if not context_chunks:
            return RAGResponse(
                answer="I don't have enough information to answer that question. "
                       "Try asking about Morad's skills, projects, or experience.",
                sources=[],
                cached=False,
                model=self.llm_client.model,
            )

        result = self.llm_client.generate(question, context_chunks, use_cache=use_cache)

        if "error" in result:
            return RAGResponse(
                answer=result["error"],
                sources=sources,
                cached=False,
                model=self.llm_client.model,
                error=result["error"],
            )

        return RAGResponse(
            answer=result["response"],
            sources=sources,
            cached=result.get("cached", False),
            model=result.get("model", ""),
            latency_s=result.get("latency_s"),
        )

    # ── Streaming RAG ─────────────────────────────────────────────────────────
    def stream(self, question: str) -> Generator[str, None, None]:
        context_chunks, sources = self.retrieve(question)

        if not context_chunks:
            yield "I don't have enough information to answer that. Try asking about Morad's skills or projects."
            return

        # Yield sources metadata as first SSE chunk
        import json
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        # Stream tokens
        for token in self.llm_client.stream(question, context_chunks):
            yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ── Singleton ──────────────────────────────────────────────────────────────────
_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
