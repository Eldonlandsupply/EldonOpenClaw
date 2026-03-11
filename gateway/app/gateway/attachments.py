"""
Attachment intake.
Downloads and validates files from Telegram.
OPEN ITEM: OCR/content extraction not yet implemented.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

from ..gateway.models import AttachmentMeta

MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

ALLOWED_MIME_PREFIXES = {
    "image/",
    "application/pdf",
    "text/",
    "application/json",
    "application/vnd.openxmlformats",
}

DATA_DIR = os.getenv("DATA_DIR", "./data")


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


def validate_attachment(meta: AttachmentMeta) -> tuple[bool, str]:
    """Returns (ok, reason)."""
    if meta.size_bytes and meta.size_bytes > MAX_SIZE_BYTES:
        return False, f"File too large: {meta.size_bytes} bytes (max {MAX_SIZE_BYTES})"

    if meta.mime_type:
        if not any(meta.mime_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
            return False, f"Mime type not allowed: {meta.mime_type}"

    return True, "ok"


def get_attachment_path(meta: AttachmentMeta) -> Path:
    attachments_dir = Path(DATA_DIR) / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(meta.file_name or meta.file_id)
    return attachments_dir / safe_name


async def process_attachment(meta: AttachmentMeta, raw_bytes: Optional[bytes] = None) -> dict:
    """
    Validate and save an attachment.
    Returns a record dict for the audit log.
    OPEN ITEM: content extraction / OCR / routing to summary pipeline.
    """
    ok, reason = validate_attachment(meta)
    if not ok:
        return {"status": "rejected", "reason": reason, "file_id": meta.file_id}

    record: dict = {
        "status": "accepted",
        "file_id": meta.file_id,
        "file_name": meta.file_name,
        "mime_type": meta.mime_type,
        "size_bytes": meta.size_bytes,
        "local_path": None,
        "sha256": None,
        "extraction": "OPEN_ITEM: not yet implemented",
    }

    if raw_bytes:
        path = get_attachment_path(meta)
        path.write_bytes(raw_bytes)
        record["local_path"] = str(path)
        record["sha256"] = hashlib.sha256(raw_bytes).hexdigest()
        meta.local_path = str(path)

    return record
