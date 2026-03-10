"""
pipeline.py -- top-level KMZ/KML ingest entry point

Calling convention
------------------
    from src.ingest.pipeline import ingest_kmz, IngestResult

    result = ingest_kmz(Path("parcels.kmz"))
    for feat in result.features:
        print(feat.raw.name, feat.geometry.area)

Everything fails loudly. The caller receives either an IngestResult or an
exception. No partial state is returned on failure unless partial_ok=True
is explicitly passed.

Run isolation
-------------
Each call creates a fresh temporary directory for extraction. The directory
is removed on success. On failure it is preserved for forensic inspection
and its path is included in the exception message.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .errors import IngestError
from .geometry_validator import ValidatedFeature, validate_features
from .kml_parser import parse_kml, DEFAULT_ALLOWED_GEOM
from .kmz_extractor import extract_kmz

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """
    Completed ingest result.

    Fields
    ------
    source_path:    Absolute path of the input .kmz or .kml file.
    kml_name:       Name of the primary KML file extracted.
    features:       Validated features in document order.
    assumption_log: Human-readable list of every ASSUMPTION made during
                    ingest (CRS, geometry repairs). Include in outputs for
                    traceability.
    """
    source_path: Path
    kml_name: str
    features: list[ValidatedFeature]
    assumption_log: list[str] = field(default_factory=list)

    @property
    def feature_count(self) -> int:
        return len(self.features)

    @property
    def repaired_count(self) -> int:
        return sum(1 for f in self.features if f.was_repaired)


def ingest_kmz(
    input_path: Path,
    *,
    kml_hint: str | None = None,
    allowed_geom_types: frozenset[str] = DEFAULT_ALLOWED_GEOM,
    repair_ok: bool = False,
    partial_ok: bool = False,
) -> IngestResult:
    """
    Full ingest pipeline: extract KMZ -> parse KML -> validate geometry.

    Parameters
    ----------
    input_path:
        .kmz file (zipped KML) or a bare .kml file. Must exist.
    kml_hint:
        If the KMZ contains multiple .kml files, the entry name to use as
        primary (e.g. "doc.kml"). Ignored for bare .kml input.
    allowed_geom_types:
        Geometry types to accept. Default: {'Polygon', 'MultiGeometry'}.
        Others raise UnsupportedGeometryError.
    repair_ok:
        If True, invalid geometries are repaired with shapely buffer(0) and
        the repair is logged as ASSUMPTION[GEOMETRY_REPAIR].
        If False (default), invalid geometries raise GeometryError.
    partial_ok:
        If True, individual Placemark failures are skipped (logged as
        warnings). The IngestResult contains only successful features.
        If False (default), any failure raises PartialSuccessError.

    Raises
    ------
    FileNotFoundError    -- input_path does not exist.
    IngestError subclass -- see errors.py for the full taxonomy.
    """
    input_path = input_path.resolve()
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}. "
            "Verify the path and try again."
        )

    suffix = input_path.suffix.lower()
    if suffix not in {".kmz", ".kml"}:
        raise IngestError(
            f"Unsupported file extension: {suffix!r} for {input_path.name}. "
            "Expected .kmz or .kml."
        )

    logger.info("=== INGEST START: %s ===", input_path.name)
    assumption_log: list[str] = []

    # -- CRS assumption (always applies) ------------------------------------
    crs_note = (
        f"ASSUMPTION[CRS]: {input_path.name} -- all coordinates treated as "
        "EPSG:4326 (WGS-84 lon,lat) per KML specification."
    )
    assumption_log.append(crs_note)

    tmp_dir: Path | None = None

    try:
        if suffix == ".kmz":
            tmp_dir = Path(tempfile.mkdtemp(prefix="openclaw_ingest_"))
            logger.debug("Extraction temp dir: %s", tmp_dir)
            kml_path = extract_kmz(input_path, tmp_dir, kml_hint=kml_hint)
        else:
            # Bare KML -- skip extraction
            kml_path = input_path
            logger.info("Input is bare KML, skipping extraction.")

        # -- Parse ----------------------------------------------------------
        raw_features = parse_kml(
            kml_path,
            allowed_geom_types=allowed_geom_types,
            partial_ok=partial_ok,
        )

        # -- Validate -------------------------------------------------------
        validated = validate_features(
            raw_features,
            repair_ok=repair_ok,
            partial_ok=partial_ok,
        )

        # Collect repair notes into assumption log
        for vf in validated:
            if vf.repair_note:
                assumption_log.append(vf.repair_note)

        # -- Cleanup temp dir on success ------------------------------------
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            logger.debug("Removed temp dir: %s", tmp_dir)

        result = IngestResult(
            source_path=input_path,
            kml_name=kml_path.name,
            features=validated,
            assumption_log=assumption_log,
        )

        logger.info(
            "=== INGEST COMPLETE: %s | features=%d repaired=%d assumptions=%d ===",
            input_path.name,
            result.feature_count,
            result.repaired_count,
            len(assumption_log),
        )
        if assumption_log:
            logger.warning(
                "ASSUMPTIONS made during ingest of %s:\n%s",
                input_path.name,
                "\n".join(f"  {a}" for a in assumption_log),
            )

        return result

    except IngestError:
        if tmp_dir is not None and tmp_dir.exists():
            logger.error(
                "Ingest failed. Temp dir preserved for inspection: %s", tmp_dir
            )
        raise
    except Exception as exc:
        if tmp_dir is not None and tmp_dir.exists():
            logger.error(
                "Unexpected error during ingest. Temp dir preserved: %s", tmp_dir
            )
        raise IngestError(
            f"Unexpected error ingesting {input_path.name}: {exc}. "
            "This is likely a bug -- please report it with the temp dir contents."
        ) from exc
