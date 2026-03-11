"""
capture_candidates.py

Analyzes OpenClaw message history and action logs to detect repetitive
patterns that should become formalized actions.

Writes new candidates to action_candidates.json for human review.

Usage:
    python scripts/capture_candidates.py [--log-path PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CANDIDATES_FILE = Path(__file__).parent.parent / "action_candidates.json"

# Patterns that suggest a recurring task worth automating
CANDIDATE_PATTERNS = [
    (r"follow.?up",              "follow_up_automation"),
    (r"remind",                  "reminder_automation"),
    (r"status (update|check)",   "status_check_automation"),
    (r"send.*email",             "email_send_automation"),
    (r"draft.*email",            "email_draft_automation"),
    (r"check.*invoice",          "invoice_check_automation"),
    (r"track.*deadline",         "deadline_tracking"),
    (r"summarize",               "summary_generation"),
    (r"extract.*action",         "action_extraction"),
    (r"schedule.*meeting",       "meeting_scheduling"),
    (r"prepare.*dossier",        "dossier_generation"),
    (r"collect.*document",       "document_collection"),
    (r"report.*status",          "status_reporting"),
    (r"check.*permit",           "permit_followup"),
    (r"update.*crm",             "crm_update"),
]


def load_log(log_path: Path) -> list[dict]:
    """Load a JSONL audit log or plain text log."""
    entries = []
    if not log_path.exists():
        return entries
    for line in log_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"raw": line})
    return entries


def extract_text_from_entry(entry: dict) -> str:
    """Pull searchable text out of a log entry."""
    parts = []
    for key in ("message", "action", "args", "raw", "description"):
        if key in entry:
            parts.append(str(entry[key]))
    return " ".join(parts).lower()


def detect_candidates(entries: list[dict]) -> list[dict]:
    """Count pattern matches and flag patterns that appear 3+ times."""
    counts: Counter = Counter()
    for entry in entries:
        text = extract_text_from_entry(entry)
        for pattern, label in CANDIDATE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                counts[label] += 1

    candidates = []
    for label, count in counts.items():
        if count >= 3:
            candidates.append({
                "candidate_id": f"CAND-{abs(hash(label)) % 10000:04d}",
                "pattern_label": label,
                "detection_count": count,
                "status": "proposed",
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "notes": f"Detected {count} occurrences in log. Review for formalization.",
            })
    return candidates


def merge_candidates(existing: list[dict], new_candidates: list[dict]) -> list[dict]:
    """Merge new candidates; update counts for existing ones."""
    existing_labels = {c["pattern_label"]: i for i, c in enumerate(existing)}
    for cand in new_candidates:
        label = cand["pattern_label"]
        if label in existing_labels:
            idx = existing_labels[label]
            existing[idx]["detection_count"] = max(
                existing[idx]["detection_count"], cand["detection_count"]
            )
            existing[idx]["last_seen"] = cand["detected_at"]
        else:
            existing.append(cand)
    return existing


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture automation candidates from logs")
    parser.add_argument("--log-path", default="data/audit_log.jsonl", help="Path to audit log")
    args = parser.parse_args()

    log_path = Path(args.log_path)
    print(f"Scanning log: {log_path}")

    entries = load_log(log_path)
    if not entries:
        print(f"No log entries found at {log_path}. Nothing to analyze.")
        sys.exit(0)

    print(f"Loaded {len(entries)} log entries.")
    new_candidates = detect_candidates(entries)
    print(f"Detected {len(new_candidates)} candidate patterns (threshold: 3+ occurrences).")

    existing = []
    if CANDIDATES_FILE.exists():
        existing = json.loads(CANDIDATES_FILE.read_text())

    merged = merge_candidates(existing, new_candidates)
    CANDIDATES_FILE.write_text(json.dumps(merged, indent=2))
    print(f"Candidates file updated: {len(merged)} total candidates.")

    for c in new_candidates:
        print(f"  [{c['candidate_id']}] {c['pattern_label']}: {c['detection_count']} occurrences")


if __name__ == "__main__":
    main()
