"""
kmz_extractor.py -- safe KMZ extraction

Zip slip defense
----------------
A malicious or malformed KMZ can contain entries whose names include
path traversal sequences (e.g. "../../etc/passwd"). zipfile.extractall()
does NOT protect against this on all Python versions / platforms.

We defend by:
  1. Resolving each entry's target path with Path.resolve().
  2. Asserting the resolved path starts with the resolved extraction root.
  3. Aborting immediately on the first violation (ZipSlipError).

No entry is written to disk before this check passes.

We do NOT use extractall(). We extract entry-by-entry with open() + write
so the check runs before any bytes hit the filesystem.
"""
from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path

from .errors import ZipSlipError, NoKMLError, MultipleKMLError

logger = logging.getLogger(__name__)


def _assert_safe_path(entry_name: str, root: Path) -> Path:
    """
    Resolve the output path for a zip entry and verify it stays inside root.

    Raises ZipSlipError immediately if the resolved path escapes root.
    Returns the safe absolute target path.
    """
    # Normalise the entry name: zipfile uses forward slashes on all platforms.
    # We convert to the OS separator only after joining with root.
    target = (root / entry_name).resolve()
    root_resolved = root.resolve()

    # str comparison on resolved absolute paths is reliable cross-platform.
    if not str(target).startswith(str(root_resolved) + os.sep) and target != root_resolved:
        raise ZipSlipError(
            f"Zip slip detected: entry {entry_name!r} resolves to {target}, "
            f"which is outside extraction root {root_resolved}. "
            "This KMZ may be malicious. Extraction aborted. No files were written."
        )
    return target


def extract_kmz(
    kmz_path: Path,
    dest_dir: Path,
    *,
    kml_hint: str | None = None,
) -> Path:
    """
    Extract a KMZ into dest_dir and return the path of the primary KML.

    Parameters
    ----------
    kmz_path:
        Path to the .kmz file.
    dest_dir:
        Directory to extract into. Created if absent. Must not already
        contain files from a previous run (caller's responsibility to
        use a fresh temp dir).
    kml_hint:
        If the KMZ contains multiple .kml files, pass the exact entry name
        (e.g. "doc.kml") to select the primary. If omitted and multiple KMLs
        are present, MultipleKMLError is raised.

    Returns
    -------
    Path to the extracted primary .kml file.

    Raises
    ------
    ZipSlipError         -- path traversal detected; no files written.
    NoKMLError           -- no .kml entry found in the archive.
    MultipleKMLError     -- multiple .kml entries and kml_hint not supplied.
    zipfile.BadZipFile   -- archive is corrupt or not a zip.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(kmz_path, "r") as zf:
        all_entries = zf.namelist()
        logger.debug("KMZ %s contains %d entries: %s", kmz_path.name, len(all_entries), all_entries)

        # -- Phase 1: security scan before any extraction --------------------
        for entry_name in all_entries:
            _assert_safe_path(entry_name, dest_dir)

        # -- Phase 2: extract every entry -----------------------------------
        for entry_name in all_entries:
            target = _assert_safe_path(entry_name, dest_dir)  # re-check (defence in depth)

            if entry_name.endswith("/"):
                # directory entry
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(entry_name) as src, open(target, "wb") as dst:
                dst.write(src.read())

        logger.info("Extracted %d entries from %s to %s", len(all_entries), kmz_path.name, dest_dir)

        # -- Phase 3: locate primary KML ------------------------------------
        kml_entries = [e for e in all_entries if e.lower().endswith(".kml")]

        if not kml_entries:
            raise NoKMLError(
                f"No .kml file found in {kmz_path.name}. "
                "Entries present: " + ", ".join(all_entries or ["(empty archive)"])
            )

        if len(kml_entries) == 1:
            primary = kml_entries[0]
        elif kml_hint is not None:
            if kml_hint not in kml_entries:
                raise NoKMLError(
                    f"kml_hint={kml_hint!r} not found in archive. "
                    "Available KMLs: " + ", ".join(kml_entries)
                )
            primary = kml_hint
        else:
            raise MultipleKMLError(
                f"{kmz_path.name} contains {len(kml_entries)} KML files: "
                + ", ".join(kml_entries)
                + ". Pass kml_hint=<entry_name> to select one explicitly."
            )

        kml_path = dest_dir / primary
        logger.info("Primary KML: %s", kml_path)
        return kml_path
