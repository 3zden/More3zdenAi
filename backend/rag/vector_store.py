"""
FAISS Vector Index
Embeds document chunks using sentence-transformers and builds a FAISS index
for fast semantic similarity search.
"""
import json
import os
import pickle
from pathlib import Path
from typing import List, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from .loader import DocumentChunk, load_knowledge_base

# ── Configuration ──────────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "/app/data/faiss.index")
CHUNKS_PATH = os.getenv("FAISS_CHUNKS_PATH", "/app/data/chunks.pkl")
KNOWLEDGE_BASE_DIR = os.getenv("KNOWLEDGE_BASE_DIR", "/app/knowledge_base")


class FAISSVectorStore:
    """
    Manages FAISS index lifecycle:
    - build()  → embed chunks & write index to disk
    - load()   → read index from disk
    - search() → top-k semantic nearest neighbours
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model_name = model_name
        self.model: SentenceTransformer | None = None
        self.index: faiss.Index | None = None
        self.chunks: List[DocumentChunk] = []

    # ── Lazy-load the embedding model ─────────────────────────────────────────
    def _get_model(self) -> SentenceTransformer:
        if self.model is None:
            print(f"[FAISS] Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
        return self.model

    # ── Embed a list of strings ────────────────────────────────────────────────
    def embed(self, texts: List[str]) -> np.ndarray:
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
        return embeddings.astype("float32")

    # ── Build index from knowledge base ───────────────────────────────────────
    def build(
        self,
        knowledge_base_dir: str = KNOWLEDGE_BASE_DIR,
        index_path: str = INDEX_PATH,
        chunks_path: str = CHUNKS_PATH,
    ) -> None:
        print("[FAISS] Building vector index...")

        # Load & chunk documents
        self.chunks = load_knowledge_base(knowledge_base_dir)
        if not self.chunks:
            raise ValueError("No chunks found. Check your knowledge base directory.")

        texts = [chunk.content for chunk in self.chunks]

        # Embed
        print(f"[FAISS] Embedding {len(texts)} chunks...")
        embeddings = self.embed(texts)

        # Build inner-product index (cosine similarity because we normalize)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)

        # Persist
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        faiss.write_index(self.index, index_path)
        with open(chunks_path, "wb") as f:
            pickle.dump(self.chunks, f)

        print(f"[FAISS] Index saved → {index_path} ({self.index.ntotal} vectors, dim={dim})")

    # ── Load existing index from disk ─────────────────────────────────────────
    def load(
        self,
        index_path: str = INDEX_PATH,
        chunks_path: str = CHUNKS_PATH,
    ) -> None:
        if not os.path.exists(index_path):
            raise FileNotFoundError(
                f"FAISS index not found at {index_path}. Run build() first."
            )
        print(f"[FAISS] Loading index from {index_path}")
        self.index = faiss.read_index(index_path)
        with open(chunks_path, "rb") as f:
            self.chunks = pickle.load(f)
        print(f"[FAISS] Loaded {self.index.ntotal} vectors, {len(self.chunks)} chunks")

    # ── Semantic search ────────────────────────────────────────────────────────
    def search(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[DocumentChunk, float]]:
        if self.index is None:
            raise RuntimeError("Index not loaded. Call build() or load() first.")

        query_vec = self.embed([query])
        scores, indices = self.index.search(query_vec, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            results.append((self.chunks[idx], float(score)))

        return results

    # ── Convenience: rebuild if stale, otherwise load ─────────────────────────
    def load_or_build(
        self,
        knowledge_base_dir: str = KNOWLEDGE_BASE_DIR,
        index_path: str = INDEX_PATH,
        chunks_path: str = CHUNKS_PATH,
    ) -> None:
        if os.path.exists(index_path) and os.path.exists(chunks_path):
            self.load(index_path, chunks_path)
        else:
            self.build(knowledge_base_dir, index_path, chunks_path)


# ── Singleton for use across Django app ───────────────────────────────────────
_vector_store: FAISSVectorStore | None = None


def get_vector_store() -> FAISSVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = FAISSVectorStore()
        _vector_store.load_or_build()
    return _vector_store


if __name__ == "__main__":
    store = FAISSVectorStore()
    store.build(
        knowledge_base_dir="../../knowledge_base",
        index_path="../../data/faiss.index",
        chunks_path="../../data/chunks.pkl",
    )
    results = store.search("What technologies do you use?", top_k=3)
    for chunk, score in results:
        print(f"\n[{score:.3f}] {chunk.section}\n{chunk.content[:150]}")
