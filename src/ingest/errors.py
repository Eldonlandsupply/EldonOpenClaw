"""
All ingest errors are explicit subtypes of IngestError.
No caller should ever catch the base Exception for ingestion work.

Principle: fail loudly with an actionable message. Every error must tell
the operator what went wrong, which file or layer caused it, and what to
do next.
"""
from __future__ import annotations


class IngestError(Exception):
    """Base for all ingest failures."""


class ZipSlipError(IngestError):
    """
    A zip entry resolves to a path outside the extraction root.
    This is a security violation -- abort unconditionally.
    """


class MultipleKMLError(IngestError):
    """
    KMZ contained more than one .kml file and no explicit primary was named.
    Caller must pass kml_hint= to select one, or pre-process the KMZ.
    """


class NoKMLError(IngestError):
    """KMZ contained no .kml file at any depth."""


class KMLParseError(IngestError):
    """XML in the KML is malformed or otherwise unparseable."""


class NamespaceError(IngestError):
    """
    KML uses an unrecognised namespace root. Whitelisted namespaces are
    listed in kml_parser.KNOWN_NS. Add to the whitelist only after manual
    review of the file.
    """


class CRSError(IngestError):
    """
    A geometry arrived with an explicit CRS that is not EPSG:4326, and
    silent reprojection is disabled. Reproject the source file first, or
    enable explicit reprojection in ingest config (logs an ASSUMPTION).
    """


class GeometryError(IngestError):
    """
    A geometry is invalid and automatic repair is disabled, or repair
    was attempted but produced an empty or degenerate result.
    """


class UnsupportedGeometryError(IngestError):
    """
    A Placemark geometry type is present but not in the allowed set.
    Allowed types: Polygon, MultiPolygon (configurable).
    Found type is included in the message.
    """


class PartialSuccessError(IngestError):
    """
    Some layers parsed, but at least one layer failed. Raised when
    partial_ok=False (default). The .failures attribute holds per-layer
    errors so the operator can triage each failure individually.
    """

    def __init__(self, message: str, failures: dict[str, Exception]) -> None:
        super().__init__(message)
        self.failures = failures

    def __str__(self) -> str:
        lines = [super().__str__()]
        for layer, exc in self.failures.items():
            lines.append(f"  layer={layer!r}: {type(exc).__name__}: {exc}")
        return "\n".join(lines)
