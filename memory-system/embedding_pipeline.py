"""
embedding_pipeline.py — multi-backend embedding with auto-fallback.

Priority: OpenRouter (text-embedding-3-small) → sentence-transformers → TF-IDF
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


# ── OpenAI-compatible (OpenRouter) ────────────────────────────────────────────

def _embed_openai(texts: List[str], cfg: dict) -> np.ndarray:
    import httpx, json

    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("No OPENROUTER_API_KEY or OPENAI_API_KEY found")

    base_url = cfg.get("openai_base_url", "https://openrouter.ai/api/v1")
    model = cfg.get("openai_embed_model", "text-embedding-3-small")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # batch in chunks of 64
    all_embeddings = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        payload = {"model": model, "input": batch}
        r = httpx.post(f"{base_url}/embeddings", headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        for item in sorted(data["data"], key=lambda x: x["index"]):
            all_embeddings.append(item["embedding"])

    return np.array(all_embeddings, dtype=np.float32)


# ── sentence-transformers ──────────────────────────────────────────────────────

def _embed_st(texts: List[str], cfg: dict) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model_name = cfg.get("st_model", "all-MiniLM-L6-v2")
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
    return np.array(embeddings, dtype=np.float32)


# ── TF-IDF fallback ───────────────────────────────────────────────────────────

_tfidf_vectorizer = None
_tfidf_matrix = None
_tfidf_texts: List[str] = []


def _embed_tfidf(texts: List[str], cfg: dict) -> np.ndarray:
    """Fit or update a TF-IDF vectorizer and return dense vectors."""
    global _tfidf_vectorizer, _tfidf_matrix, _tfidf_texts

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    if _tfidf_vectorizer is None or texts != _tfidf_texts:
        _tfidf_vectorizer = TfidfVectorizer(max_features=512, sublinear_tf=True)
        mat = _tfidf_vectorizer.fit_transform(texts)
        _tfidf_matrix = normalize(mat.toarray().astype(np.float32))
        _tfidf_texts = texts[:]

    result = _tfidf_vectorizer.transform(texts)
    from sklearn.preprocessing import normalize as norm2
    return norm2(result.toarray().astype(np.float32))


# ── Public API ────────────────────────────────────────────────────────────────

def embed_texts(texts: List[str], cfg: dict) -> np.ndarray:
    """Embed a list of texts using the best available backend."""
    backends = cfg.get("embedding_backends", ["openai", "sentence_transformers", "tfidf"])

    for backend in backends:
        try:
            if backend == "openai":
                logger.debug("Trying OpenAI-compatible embeddings ...")
                return _embed_openai(texts, cfg)
            elif backend == "sentence_transformers":
                logger.debug("Trying sentence-transformers ...")
                return _embed_st(texts, cfg)
            elif backend == "tfidf":
                logger.debug("Falling back to TF-IDF ...")
                return _embed_tfidf(texts, cfg)
        except Exception as e:
            logger.warning(f"Backend '{backend}' failed: {e}")

    raise RuntimeError("All embedding backends failed")


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]
