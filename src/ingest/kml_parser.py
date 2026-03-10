"""
kml_parser.py -- strict KML -> raw feature extraction

Rules enforced here
-------------------
- Only whitelisted KML namespace URIs are accepted. Unknown namespaces
  fail loudly with NamespaceError.
- CRS is assumed EPSG:4326 (WGS-84) because that is the KML spec.
  This assumption is logged once per file as ASSUMPTION[CRS].
  If coordinates contain an explicit srsName that is not 4326, CRSError
  is raised (we cannot safely reproject here).
- Mixed geometry types that include unsupported types raise
  UnsupportedGeometryError unless the caller explicitly passes
  allowed_geom_types to broaden the set.
- Empty Placemark (no geometry child) raises GeometryError.
- Parsing errors in individual Placemarks are collected; if any exist
  and partial_ok=False (default), PartialSuccessError is raised after
  processing the full file so the operator gets the complete picture.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from xml.etree import ElementTree as ET

from .errors import (
    CRSError,
    GeometryError,
    KMLParseError,
    NamespaceError,
    PartialSuccessError,
    UnsupportedGeometryError,
)

logger = logging.getLogger(__name__)

# Whitelisted KML namespace URIs.
# Add a new entry ONLY after manually verifying the schema variant is
# compatible with coordinate ordering lon,lat,alt (the KML spec default).
KNOWN_NS: dict[str, str] = {
    "http://www.opengis.net/kml/2.2": "kml22",
    "http://earth.google.com/kml/2.2": "kml22_google",
    "http://earth.google.com/kml/2.1": "kml21_google",
    "http://earth.google.com/kml/2.0": "kml20_google",
}

# Geometry element tag names (local name, without namespace prefix)
POLYGON_TAG = "Polygon"
MULTIGEOMETRY_TAG = "MultiGeometry"
LINESTRING_TAG = "LineString"
POINT_TAG = "Point"

# Default allowed geometry types. Everything else raises UnsupportedGeometryError.
DEFAULT_ALLOWED_GEOM = frozenset({"Polygon", "MultiGeometry"})


@dataclass
class RawCoordRing:
    """
    A single coordinate ring as parsed from KML <coordinates>.
    lon_lat_alt is a list of (lon, lat) tuples. Altitude is discarded.
    """
    tuples: list[tuple[float, float]]
    source_text: str  # original text, preserved for traceability


@dataclass
class RawPolygon:
    outer: RawCoordRing
    inners: list[RawCoordRing] = field(default_factory=list)


@dataclass
class RawFeature:
    """
    One Placemark extracted from KML. All fields are raw / unvalidated.
    Geometry validation happens in geometry_validator.py.
    """
    placemark_index: int          # 0-based position in document order
    name: str | None
    description: str | None
    extended_data: dict[str, str]  # <SimpleData name=...> key/value pairs
    geometry_type: str             # "Polygon" | "MultiGeometry"
    polygons: list[RawPolygon]     # always >= 1 for supported types
    source_kml: str                # filename only, for traceability


def _detect_namespace(root: ET.Element) -> str:
    """
    Extract the namespace URI from the root element tag and validate it.

    ElementTree represents a namespaced tag as '{uri}LocalName'.
    Returns the ns prefix key from KNOWN_NS.

    Raises NamespaceError for unknown URIs.
    """
    tag = root.tag
    if not tag.startswith("{"):
        # No namespace at all. KML without a namespace declaration is
        # technically invalid per spec.
        raise NamespaceError(
            "KML root element has no namespace declaration. "
            "Expected one of: " + ", ".join(KNOWN_NS.keys()) + ". "
            "Add this namespace to KNOWN_NS in kml_parser.py only after "
            "verifying coordinate ordering is lon,lat."
        )

    uri = tag[1:tag.index("}")]
    if uri not in KNOWN_NS:
        raise NamespaceError(
            f"KML uses unknown namespace URI: {uri!r}. "
            "Whitelisted URIs: " + ", ".join(KNOWN_NS.keys()) + ". "
            "Add to kml_parser.KNOWN_NS only after manual review."
        )
    return uri


def _ns(uri: str) -> str:
    return f"{{{uri}}}"


def _parse_coordinates(coords_el: ET.Element) -> RawCoordRing:
    """
    Parse a <coordinates> element into a RawCoordRing.

    KML coordinate format: lon,lat[,alt] tuples separated by whitespace.
    Altitude is always discarded.

    Raises GeometryError if any tuple cannot be parsed as two floats.
    """
    raw = (coords_el.text or "").strip()
    if not raw:
        raise GeometryError(
            "<coordinates> element is empty. "
            "This Placemark has no usable geometry."
        )

    tuples: list[tuple[float, float]] = []
    for i, token in enumerate(raw.split()):
        parts = token.split(",")
        if len(parts) < 2:
            raise GeometryError(
                f"Coordinate token {i} is malformed: {token!r}. "
                "Expected lon,lat[,alt]."
            )
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError as exc:
            raise GeometryError(
                f"Coordinate token {i} contains non-numeric value: {token!r}."
            ) from exc
        tuples.append((lon, lat))

    return RawCoordRing(tuples=tuples, source_text=raw)


def _parse_polygon(poly_el: ET.Element, ns: str) -> RawPolygon:
    outer_el = poly_el.find(f"{_ns(ns)}outerBoundaryIs/{_ns(ns)}LinearRing/{_ns(ns)}coordinates")
    if outer_el is None:
        raise GeometryError(
            "<Polygon> has no <outerBoundaryIs> / <LinearRing> / <coordinates> path. "
            "Polygon is structurally incomplete."
        )
    outer = _parse_coordinates(outer_el)

    inners: list[RawCoordRing] = []
    for inner_el in poly_el.findall(
        f"{_ns(ns)}innerBoundaryIs/{_ns(ns)}LinearRing/{_ns(ns)}coordinates"
    ):
        inners.append(_parse_coordinates(inner_el))

    return RawPolygon(outer=outer, inners=inners)


def _parse_placemark(
    pm_el: ET.Element,
    index: int,
    ns: str,
    source_kml: str,
    allowed_geom: frozenset[str],
) -> RawFeature:
    """Parse one <Placemark> element into a RawFeature."""
    name_el = pm_el.find(f"{_ns(ns)}name")
    name = name_el.text.strip() if name_el is not None and name_el.text else None

    desc_el = pm_el.find(f"{_ns(ns)}description")
    description = desc_el.text.strip() if desc_el is not None and desc_el.text else None

    # Extended data
    extended: dict[str, str] = {}
    for sd in pm_el.findall(f".//{_ns(ns)}SimpleData"):
        k = sd.get("name")
        if k and sd.text:
            extended[k] = sd.text.strip()

    # Geometry -- find first recognised geometry child
    poly_el = pm_el.find(f"{_ns(ns)}Polygon")
    multi_el = pm_el.find(f"{_ns(ns)}MultiGeometry")

    if poly_el is not None and POLYGON_TAG in allowed_geom:
        polygons = [_parse_polygon(poly_el, ns)]
        geom_type = POLYGON_TAG

    elif multi_el is not None and MULTIGEOMETRY_TAG in allowed_geom:
        polygons = []
        for child_poly in multi_el.findall(f"{_ns(ns)}Polygon"):
            polygons.append(_parse_polygon(child_poly, ns))
        if not polygons:
            raise GeometryError(
                f"Placemark[{index}] name={name!r}: <MultiGeometry> contains "
                "no <Polygon> children. Only Polygon children are extracted."
            )
        geom_type = MULTIGEOMETRY_TAG

    else:
        # Check what's actually there and report it
        found_tags = [
            child.tag.split("}")[-1]
            for child in pm_el
            if child.tag.split("}")[-1] in
            {POLYGON_TAG, MULTIGEOMETRY_TAG, LINESTRING_TAG, POINT_TAG}
        ]
        if not found_tags:
            raise GeometryError(
                f"Placemark[{index}] name={name!r}: no geometry element found. "
                "Expected <Polygon> or <MultiGeometry>."
            )
        found = found_tags[0]
        if found not in allowed_geom:
            raise UnsupportedGeometryError(
                f"Placemark[{index}] name={name!r}: geometry type {found!r} is not "
                f"in allowed_geom_types={set(allowed_geom)}. "
                "Pass allowed_geom_types={'LineString'} etc. to enable, or "
                "filter these Placemarks out of the source KML before ingestion."
            )
        raise GeometryError(
            f"Placemark[{index}] name={name!r}: unhandled geometry branch. "
            f"found_tags={found_tags}"
        )

    return RawFeature(
        placemark_index=index,
        name=name,
        description=description,
        extended_data=extended,
        geometry_type=geom_type,
        polygons=polygons,
        source_kml=source_kml,
    )


def parse_kml(
    kml_path: Path,
    *,
    allowed_geom_types: frozenset[str] = DEFAULT_ALLOWED_GEOM,
    partial_ok: bool = False,
) -> list[RawFeature]:
    """
    Parse a KML file and return a list of RawFeature objects.

    CRS assumption
    --------------
    KML is always WGS-84 (EPSG:4326) per the OGC spec. We log this once
    as ASSUMPTION[CRS] so it appears in the run log and can be audited.
    There is no mechanism to override it here; if a file uses a different
    CRS it must be reprojected upstream.

    Parameters
    ----------
    kml_path:        Path to the extracted .kml file.
    allowed_geom_types:
                     Geometry tag names to accept. Default: Polygon, MultiGeometry.
    partial_ok:      If False (default), raise PartialSuccessError when any
                     Placemark fails. If True, failed Placemarks are skipped
                     and logged as warnings; successful ones are returned.

    Raises
    ------
    KMLParseError          -- XML is unparseable.
    NamespaceError         -- namespace not whitelisted.
    PartialSuccessError    -- one or more Placemarks failed (partial_ok=False).
    """
    source_kml = kml_path.name

    # -- CRS assumption log -------------------------------------------------
    logger.info(
        "ASSUMPTION[CRS]: %s -- treating all coordinates as EPSG:4326 (WGS-84 lon,lat). "
        "KML spec mandates this. If the source was reprojected, verify before ingesting.",
        source_kml,
    )

    # -- Parse XML ----------------------------------------------------------
    try:
        tree = ET.parse(kml_path)
    except ET.ParseError as exc:
        raise KMLParseError(
            f"Failed to parse XML in {source_kml}: {exc}. "
            "Verify the file is valid XML (not truncated, no encoding errors)."
        ) from exc

    root = tree.getroot()
    ns_uri = _detect_namespace(root)

    # Collect all Placemarks regardless of folder depth
    placemarks = root.findall(f".//{_ns(ns_uri)}Placemark")
    logger.info("%s: found %d Placemark(s)", source_kml, len(placemarks))

    if not placemarks:
        # Not an error per se, but loud enough to notice
        logger.warning(
            "%s: 0 Placemarks found. The file is valid KML but contains no features. "
            "Check that Placemarks are not inside a NetworkLink or other unsupported container.",
            source_kml,
        )
        return []

    # -- Parse each Placemark -----------------------------------------------
    features: list[RawFeature] = []
    failures: dict[str, Exception] = {}

    for i, pm_el in enumerate(placemarks):
        label = f"Placemark[{i}]"
        try:
            feat = _parse_placemark(pm_el, i, ns_uri, source_kml, allowed_geom_types)
            features.append(feat)
            logger.debug("%s: parsed %s name=%r geom=%s", source_kml, label, feat.name, feat.geometry_type)
        except (GeometryError, UnsupportedGeometryError, CRSError) as exc:
            failures[label] = exc
            if partial_ok:
                logger.warning("%s: skipping %s -- %s: %s", source_kml, label, type(exc).__name__, exc)
            else:
                logger.error("%s: failed %s -- %s: %s", source_kml, label, type(exc).__name__, exc)

    if failures and not partial_ok:
        raise PartialSuccessError(
            f"{source_kml}: {len(failures)} of {len(placemarks)} Placemark(s) failed. "
            "Fix the issues above, or pass partial_ok=True to skip failures.",
            failures=failures,
        )

    logger.info(
        "%s: successfully parsed %d/%d Placemarks",
        source_kml, len(features), len(placemarks),
    )
    return features
