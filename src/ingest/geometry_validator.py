"""
geometry_validator.py -- validate and optionally repair geometries

Strictness rules
----------------
- Invalid geometries raise GeometryError by default (repair_ok=False).
- If repair_ok=True, shapely's buffer(0) trick is applied and the result
  is logged as ASSUMPTION[GEOMETRY_REPAIR]. If the repair produces an
  empty or wrong-type geometry, GeometryError is raised anyway.
- Self-intersecting rings are checked explicitly via shapely is_valid.
- Degenerate polygons (< 4 coordinate pairs, area == 0) always fail,
  even with repair_ok=True, because there is no safe repair.
- Coordinate range for EPSG:4326: lon in [-180, 180], lat in [-90, 90].
  Out-of-range coordinates raise GeometryError with the offending value.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from shapely.geometry import Polygon, MultiPolygon
from shapely.geometry.base import BaseGeometry

from .errors import GeometryError
from .kml_parser import RawFeature, RawPolygon, RawCoordRing

logger = logging.getLogger(__name__)

# Minimum ring length: 4 positions (3 unique + closing repeat) per OGC spec
MIN_RING_LEN = 4


@dataclass
class ValidatedFeature:
    """
    A RawFeature whose geometry has passed (or been repaired through) validation.

    Fields
    ------
    raw:            Original RawFeature for full traceability.
    geometry:       Shapely Polygon or MultiPolygon.
    was_repaired:   True if buffer(0) repair was applied (ASSUMPTION logged).
    repair_note:    Human-readable description of what repair did, or None.
    """
    raw: RawFeature
    geometry: BaseGeometry
    was_repaired: bool
    repair_note: str | None


def _validate_coord_range(ring: RawCoordRing, label: str) -> None:
    """Raise GeometryError if any coordinate is outside WGS-84 bounds."""
    for i, (lon, lat) in enumerate(ring.tuples):
        if not (-180.0 <= lon <= 180.0):
            raise GeometryError(
                f"{label}: coordinate[{i}] has lon={lon} outside [-180, 180]. "
                "Verify the source file uses EPSG:4326."
            )
        if not (-90.0 <= lat <= 90.0):
            raise GeometryError(
                f"{label}: coordinate[{i}] has lat={lat} outside [-90, 90]. "
                "Verify the source file uses EPSG:4326."
            )


def _ring_to_tuples(ring: RawCoordRing) -> list[tuple[float, float]]:
    return ring.tuples


def _build_shapely_polygon(raw_poly: RawPolygon, label: str) -> Polygon:
    """Build a shapely Polygon from a RawPolygon, validating ring lengths."""
    outer = raw_poly.outer

    if len(outer.tuples) < MIN_RING_LEN:
        raise GeometryError(
            f"{label}: outer ring has {len(outer.tuples)} coordinate(s); "
            f"minimum is {MIN_RING_LEN} (3 unique + 1 closing). "
            "This polygon is degenerate and cannot be repaired."
        )

    _validate_coord_range(outer, f"{label} outer ring")

    holes: list[list[tuple[float, float]]] = []
    for j, inner in enumerate(raw_poly.inners):
        if len(inner.tuples) < MIN_RING_LEN:
            raise GeometryError(
                f"{label}: inner ring[{j}] has {len(inner.tuples)} coordinate(s); "
                f"minimum is {MIN_RING_LEN}. This hole is degenerate and cannot be repaired."
            )
        _validate_coord_range(inner, f"{label} inner ring[{j}]")
        holes.append(_ring_to_tuples(inner))

    return Polygon(_ring_to_tuples(outer), holes)


def _repair(geom: BaseGeometry, label: str, expected_type: type) -> BaseGeometry:
    """
    Apply buffer(0) repair. Logs ASSUMPTION. Raises GeometryError if
    the result is empty or the wrong type.
    """
    repaired = geom.buffer(0)
    note = (
        f"ASSUMPTION[GEOMETRY_REPAIR]: {label} was invalid (likely self-intersecting). "
        "Applied shapely buffer(0) repair. Verify output polygon matches source intent."
    )
    logger.warning(note)

    if repaired.is_empty:
        raise GeometryError(
            f"{label}: buffer(0) repair produced an empty geometry. "
            "The polygon may be entirely degenerate. Manual inspection required."
        )
    if not isinstance(repaired, expected_type):
        raise GeometryError(
            f"{label}: buffer(0) repair changed geometry type from "
            f"{type(geom).__name__} to {type(repaired).__name__}. "
            "This is unexpected; manual inspection required."
        )
    return repaired, note


def validate_feature(
    raw: RawFeature,
    *,
    repair_ok: bool = False,
) -> ValidatedFeature:
    """
    Validate the geometry in a RawFeature and return a ValidatedFeature.

    Parameters
    ----------
    raw:        RawFeature from kml_parser.parse_kml().
    repair_ok:  If True, attempt buffer(0) repair on invalid geometries and
                log an ASSUMPTION. If False (default), raise GeometryError
                on any invalid geometry.

    Raises
    ------
    GeometryError  -- geometry is invalid and repair is disabled, or repair
                      produced an unusable result.
    """
    label = f"Placemark[{raw.placemark_index}] name={raw.name!r} source={raw.source_kml}"

    if raw.geometry_type == "Polygon":
        if len(raw.polygons) != 1:
            raise GeometryError(
                f"{label}: geometry_type=Polygon but polygons list has "
                f"{len(raw.polygons)} entries. Parser invariant violated."
            )
        shp = _build_shapely_polygon(raw.polygons[0], label)

        if not shp.is_valid:
            if not repair_ok:
                raise GeometryError(
                    f"{label}: polygon is invalid (e.g. self-intersection or zero area). "
                    "Pass repair_ok=True to attempt buffer(0) repair, "
                    "or fix the source geometry."
                )
            shp, note = _repair(shp, label, Polygon)
            # After repair, confirm non-degenerate
            if shp.area == 0.0:
                raise GeometryError(
                    f"{label}: buffer(0) repair produced zero-area polygon. "
                    "Degenerate geometry; cannot be fixed automatically."
                )
            return ValidatedFeature(raw=raw, geometry=shp, was_repaired=True, repair_note=note)

        if shp.area == 0.0:
            raise GeometryError(
                f"{label}: polygon has zero area. "
                "Degenerate geometry; cannot be repaired safely."
            )

        return ValidatedFeature(raw=raw, geometry=shp, was_repaired=False, repair_note=None)

    elif raw.geometry_type == "MultiGeometry":
        parts: list[Polygon] = []
        for k, raw_poly in enumerate(raw.polygons):
            part_label = f"{label} poly[{k}]"
            shp = _build_shapely_polygon(raw_poly, part_label)

            if shp.area == 0.0:
                raise GeometryError(
                    f"{part_label}: part polygon has zero area. "
                    "Degenerate geometry; cannot be repaired safely."
                )

            if not shp.is_valid:
                if not repair_ok:
                    raise GeometryError(
                        f"{part_label}: part polygon is invalid (e.g. self-intersection). "
                        "Pass repair_ok=True to attempt buffer(0) repair, "
                        "or fix the source geometry."
                    )
                shp, _note = _repair(shp, part_label, Polygon)
            parts.append(shp)

        multi = MultiPolygon(parts)
        if not multi.is_valid:
            if not repair_ok:
                raise GeometryError(
                    f"{label}: assembled MultiPolygon is invalid. "
                    "Pass repair_ok=True to attempt buffer(0) repair."
                )
            multi, note = _repair(multi, label, MultiPolygon)
            return ValidatedFeature(raw=raw, geometry=multi, was_repaired=True, repair_note=note)

        return ValidatedFeature(raw=raw, geometry=multi, was_repaired=False, repair_note=None)

    else:
        raise GeometryError(
            f"{label}: unhandled geometry_type={raw.geometry_type!r}. "
            "This is a parser bug -- please report it."
        )


def validate_features(
    features: list[RawFeature],
    *,
    repair_ok: bool = False,
    partial_ok: bool = False,
) -> list[ValidatedFeature]:
    """
    Validate a list of RawFeatures. Mirrors kml_parser.parse_kml semantics:
    partial_ok=False raises PartialSuccessError on any failure.
    """
    from .errors import PartialSuccessError

    validated: list[ValidatedFeature] = []
    failures: dict[str, Exception] = {}

    for raw in features:
        label = f"Placemark[{raw.placemark_index}]"
        try:
            vf = validate_feature(raw, repair_ok=repair_ok)
            validated.append(vf)
        except GeometryError as exc:
            failures[label] = exc
            if partial_ok:
                logger.warning("geometry validation skipped %s: %s", label, exc)
            else:
                logger.error("geometry validation failed %s: %s", label, exc)

    if failures and not partial_ok:
        from .errors import PartialSuccessError
        raise PartialSuccessError(
            f"{len(failures)} of {len(features)} feature(s) failed geometry validation. "
            "Fix the issues above, or pass partial_ok=True to skip failed features.",
            failures=failures,
        )

    return validated
