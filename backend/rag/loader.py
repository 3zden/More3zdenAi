"""
Document Loader & Chunker
Loads markdown/text files from the knowledge base and splits them into
semantic chunks ready for embedding.
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class DocumentChunk:
    chunk_id: str
    source: str
    section: str
    content: str
    metadata: dict


def load_markdown_file(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def split_into_chunks(
    text: str,
    source: str,
    max_chunk_size: int = 500,
    overlap: int = 50,
) -> List[DocumentChunk]:
    """
    Split a markdown document into semantic chunks.
    Tries to split on section headers first, then falls back to
    sliding window on long sections.
    """
    chunks: List[DocumentChunk] = []

    # Split on markdown headers (##, ###, #)
    header_pattern = re.compile(r"^(#{1,3} .+)$", re.MULTILINE)
    parts = header_pattern.split(text)

    # Pair headers with their content
    sections = []
    current_header = "General"
    buffer = []

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if re.match(r"^#{1,3} ", part):
            if buffer:
                sections.append((current_header, " ".join(buffer)))
                buffer = []
            current_header = part.lstrip("#").strip()
        else:
            buffer.append(part)

    if buffer:
        sections.append((current_header, " ".join(buffer)))

    # For each section, apply sliding window if too long
    for section_title, section_text in sections:
        words = section_text.split()
        if len(words) <= max_chunk_size:
            chunk_id = f"{source}::{section_title}::0"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    source=source,
                    section=section_title,
                    content=section_text,
                    metadata={"source": source, "section": section_title},
                )
            )
        else:
            # Sliding window
            start = 0
            idx = 0
            while start < len(words):
                end = min(start + max_chunk_size, len(words))
                chunk_text = " ".join(words[start:end])
                chunk_id = f"{source}::{section_title}::{idx}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        source=source,
                        section=section_title,
                        content=chunk_text,
                        metadata={"source": source, "section": section_title, "chunk_idx": idx},
                    )
                )
                start += max_chunk_size - overlap
                idx += 1

    return chunks


def load_knowledge_base(knowledge_base_dir: str) -> List[DocumentChunk]:
    """Load all .md and .txt files from a directory and chunk them."""
    all_chunks: List[DocumentChunk] = []
    kb_path = Path(knowledge_base_dir)

    for filepath in kb_path.rglob("*.md"):
        text = load_markdown_file(str(filepath))
        source = filepath.stem
        chunks = split_into_chunks(text, source=source)
        all_chunks.extend(chunks)
        print(f"[Loader] {filepath.name} → {len(chunks)} chunks")

    for filepath in kb_path.rglob("*.txt"):
        text = load_markdown_file(str(filepath))
        source = filepath.stem
        chunks = split_into_chunks(text, source=source)
        all_chunks.extend(chunks)
        print(f"[Loader] {filepath.name} → {len(chunks)} chunks")

    print(f"[Loader] Total chunks loaded: {len(all_chunks)}")
    return all_chunks


if __name__ == "__main__":
    chunks = load_knowledge_base("../../knowledge_base")
    for c in chunks[:3]:
        print(f"\n--- {c.chunk_id} ---\n{c.content[:200]}")
