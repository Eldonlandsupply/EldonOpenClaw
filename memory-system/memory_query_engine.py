"""
memory_query_engine.py — query the semantic index.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import yaml

from embedding_pipeline import embed_texts
from repo_indexer import get_vector_store, load_config

logger = logging.getLogger(__name__)


def memory_search(query: str, cfg: dict, top_k: Optional[int] = None) -> List[dict]:
    """
    Convert query to embedding, search vector store, return ranked results.

    Returns:
        [
          {
            "repo": str,
            "file": str,
            "function": str,
            "score": float,
            "code_snippet": str,
            "start_line": int,
            "language": str,
          },
          ...
        ]
    """
    k = top_k or cfg.get("top_k", 8)
    store = get_vector_store(cfg)

    try:
        embeddings = embed_texts([query], cfg)
    except Exception as e:
        logger.error(f"Embedding query failed: {e}")
        return []

    query_vec = embeddings[0]
    results = store.query(query_vec, top_k=k)

    output = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
        # Chroma cosine distance is 0=identical, 2=opposite
        # Convert to similarity score 0–1
        score = round(1 - (float(dist) / 2), 4)

        output.append({
            "repo": meta.get("repo", ""),
            "file": meta.get("file", ""),
            "function": meta.get("function", ""),
            "score": score,
            "code_snippet": doc[:500] if doc else "",
            "start_line": meta.get("start_line", 0),
            "language": meta.get("language", ""),
        })

    # Sort by score descending
    output.sort(key=lambda x: x["score"], reverse=True)
    return output


def search_repo_memory(query: str, config_path: str = "config.yaml") -> List[dict]:
    """Public callable for OpenClaw agents."""
    cfg = load_config(config_path)
    return memory_search(query, cfg)
