"""
repo_indexer.py — discovers all git repos under repo_root, chunks files,
generates embeddings, and persists to the vector store.
"""
from __future__ import annotations

import fnmatch
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Generator, List, Optional

import yaml

from embedding_pipeline import embed_texts, text_hash

logger = logging.getLogger(__name__)


# ── Config loader ─────────────────────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── Repo discovery ────────────────────────────────────────────────────────────

def discover_repos(repo_root: str) -> List[Path]:
    root = Path(repo_root).expanduser()
    repos = []
    for item in root.iterdir():
        if item.is_dir() and (item / ".git").exists():
            repos.append(item)
    logger.info(f"Discovered {len(repos)} repos under {root}")
    return repos


def get_repo_head(repo: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return None


# ── File filtering ────────────────────────────────────────────────────────────

def should_index(path: Path, include_exts: List[str], exclude_patterns: List[str]) -> bool:
    # Check extension
    if path.suffix not in include_exts:
        return False
    # Check exclusion patterns against all path parts
    parts = path.parts
    for pattern in exclude_patterns:
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return False
    # Never index secret files
    name = path.name.lower()
    if name in (".env", "secrets.yaml", "secrets.json"):
        return False
    return True


def iter_repo_files(repo: Path, cfg: dict) -> Generator[Path, None, None]:
    include_exts = cfg.get("include_extensions", [".py", ".md"])
    exclude_patterns = cfg.get("exclude_patterns", ["node_modules", ".git"])
    for path in repo.rglob("*"):
        if path.is_file() and should_index(path, include_exts, exclude_patterns):
            yield path


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_python(content: str, file_path: str) -> List[dict]:
    """Split Python into function/class blocks, fall back to sliding window."""
    import ast
    chunks = []
    try:
        tree = ast.parse(content)
        lines = content.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", start + 20)
                snippet = "\n".join(lines[start:end])
                chunks.append({
                    "function": node.name,
                    "content": snippet,
                    "start_line": start + 1,
                })
    except SyntaxError:
        pass

    if not chunks:
        chunks = _sliding_window(content, file_path)
    return chunks


def _sliding_window(content: str, file_path: str, size: int = 60, overlap: int = 10) -> List[dict]:
    lines = content.splitlines()
    chunks = []
    i = 0
    while i < len(lines):
        chunk_lines = lines[i : i + size]
        chunks.append({
            "function": None,
            "content": "\n".join(chunk_lines),
            "start_line": i + 1,
        })
        i += size - overlap
    return chunks


def chunk_markdown(content: str) -> List[dict]:
    """Split markdown by headings."""
    sections = []
    current_heading = "intro"
    current_lines: List[str] = []

    for line in content.splitlines():
        if line.startswith("#"):
            if current_lines:
                sections.append({"function": current_heading, "content": "\n".join(current_lines), "start_line": 0})
            current_heading = line.lstrip("#").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({"function": current_heading, "content": "\n".join(current_lines), "start_line": 0})

    return sections or [{"function": None, "content": content, "start_line": 1}]


def chunk_file(path: Path, content: str) -> List[dict]:
    ext = path.suffix.lower()
    if ext == ".py":
        return chunk_python(content, str(path))
    elif ext == ".md":
        return chunk_markdown(content)
    else:
        return _sliding_window(content, str(path))


# ── Vector store ──────────────────────────────────────────────────────────────

def get_vector_store(cfg: dict):
    index_dir = Path(cfg.get("index_dir", "~/.openclaw-memory")).expanduser()
    index_dir.mkdir(parents=True, exist_ok=True)
    backend = cfg.get("vector_db", "chroma")

    if backend == "chroma":
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(index_dir / "chroma"))
            collection = client.get_or_create_collection(
                name="repo_memory",
                metadata={"hnsw:space": "cosine"},
            )
            return ChromaStore(collection)
        except ImportError:
            logger.warning("chromadb not available, falling back to FAISS")

    # FAISS fallback
    return FaissStore(index_dir / "faiss")


class ChromaStore:
    def __init__(self, collection):
        self.collection = collection

    def upsert(self, ids: List[str], embeddings, metadatas: List[dict], documents: List[str]):
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            documents=documents,
        )

    def query(self, embedding, top_k: int = 8):
        results = self.collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return results

    def get_existing_ids(self) -> set:
        try:
            return set(self.collection.get()["ids"])
        except Exception:
            return set()

    def delete_by_prefix(self, prefix: str):
        try:
            all_ids = self.collection.get()["ids"]
            to_delete = [i for i in all_ids if i.startswith(prefix)]
            if to_delete:
                self.collection.delete(ids=to_delete)
        except Exception:
            pass


class FaissStore:
    """Simple FAISS-backed store with JSON metadata sidecar."""

    def __init__(self, path: Path):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.path / "index.faiss"
        self.meta_file = self.path / "meta.json"
        self._load()

    def _load(self):
        import faiss
        if self.index_file.exists():
            self.index = faiss.read_index(str(self.index_file))
            with open(self.meta_file) as f:
                self._meta = json.load(f)
        else:
            self.index = None
            self._meta = {"ids": [], "metadatas": [], "documents": []}

    def _save(self):
        import faiss
        faiss.write_index(self.index, str(self.index_file))
        with open(self.meta_file, "w") as f:
            json.dump(self._meta, f)

    def upsert(self, ids, embeddings, metadatas, documents):
        import faiss
        dim = embeddings.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatIP(dim)

        # Remove existing ids
        for id_ in ids:
            if id_ in self._meta["ids"]:
                idx = self._meta["ids"].index(id_)
                self._meta["ids"].pop(idx)
                self._meta["metadatas"].pop(idx)
                self._meta["documents"].pop(idx)

        self.index.add(embeddings)
        self._meta["ids"].extend(ids)
        self._meta["metadatas"].extend(metadatas)
        self._meta["documents"].extend(documents)
        self._save()

    def query(self, embedding, top_k: int = 8):
        if self.index is None or self.index.ntotal == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        import numpy as np
        q = np.array([embedding], dtype=np.float32)
        scores, indices = self.index.search(q, min(top_k, self.index.ntotal))
        ids = [[self._meta["ids"][i] for i in indices[0] if i >= 0]]
        docs = [[self._meta["documents"][i] for i in indices[0] if i >= 0]]
        metas = [[self._meta["metadatas"][i] for i in indices[0] if i >= 0]]
        dists = [[float(s) for s in scores[0]]]
        return {"ids": ids, "documents": docs, "metadatas": metas, "distances": dists}

    def get_existing_ids(self) -> set:
        return set(self._meta["ids"])

    def delete_by_prefix(self, prefix: str):
        pass  # rebuild on next full index


# ── State cache (tracks file hashes for incremental updates) ─────────────────

def load_state(cfg: dict) -> dict:
    state_file = Path(cfg.get("index_dir", "~/.openclaw-memory")).expanduser() / "state.json"
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {}


def save_state(cfg: dict, state: dict):
    state_file = Path(cfg.get("index_dir", "~/.openclaw-memory")).expanduser() / "state.json"
    with open(state_file, "w") as f:
        json.dump(state, f)


# ── Main indexing function ────────────────────────────────────────────────────

def index_repos(cfg: dict, force: bool = False):
    store = get_vector_store(cfg)
    state = load_state(cfg)
    repos = discover_repos(cfg.get("repo_root", "~/eldon/repos"))

    total_chunks = 0
    for repo in repos:
        repo_name = repo.name
        head = get_repo_head(repo)

        for file_path in iter_repo_files(repo, cfg):
            rel = str(file_path.relative_to(repo))
            state_key = f"{repo_name}/{rel}"

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            content_hash = text_hash(content)

            # Skip if unchanged
            if not force and state.get(state_key) == content_hash:
                continue

            chunks = chunk_file(file_path, content)
            if not chunks:
                continue

            texts = [c["content"] for c in chunks]
            try:
                embeddings = embed_texts(texts, cfg)
            except Exception as e:
                logger.warning(f"Embedding failed for {file_path}: {e}")
                continue

            ids = [f"{repo_name}::{rel}::{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "repo": repo_name,
                    "file": rel,
                    "function": c.get("function") or "",
                    "language": file_path.suffix.lstrip("."),
                    "start_line": c.get("start_line", 0),
                    "git_head": head or "",
                }
                for c in chunks
            ]

            # Remove old chunks for this file
            store.delete_by_prefix(f"{repo_name}::{rel}::")
            store.upsert(ids, embeddings, metadatas, texts)

            state[state_key] = content_hash
            total_chunks += len(chunks)
            logger.info(f"Indexed {repo_name}/{rel} — {len(chunks)} chunks")

        save_state(cfg, state)

    logger.info(f"Indexing complete. Total chunks added/updated: {total_chunks}")
    return total_chunks
