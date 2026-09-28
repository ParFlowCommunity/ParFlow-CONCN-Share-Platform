"""Display-only level layers for the original map; never grants data access."""

import gzip
import hashlib
import json
import os
from pathlib import Path
from threading import Lock

from ..common import ApiError
from ..config import BACKEND

_build_lock = Lock()


def layer_cache(level):
    if type(level) is not int or level not in range(2, 15, 2):
        raise ApiError("INVALID_INPUT")
    source = Path(os.getenv("CONCN_SHP_DIR", "")) / f"PFBAS{level}.shp"
    companions = [source.with_suffix(ext) for ext in (".shp", ".shx", ".dbf", ".prj")]
    if not all(p.is_file() for p in companions):
        raise ApiError("BOUNDARY_UNAVAILABLE", 503)
    signature = [
        (str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns) for p in companions
    ]
    key = hashlib.sha256(json.dumps(["map-v1", signature]).encode()).hexdigest()[:24]
    folder = BACKEND / "boundary_cache"
    target = folder / f"PFBAS{level}-{key}.geojson.gz"
    with _build_lock:
        if target.is_file():
            return target
        import geopandas as gpd

        frame = gpd.read_file(source)
        if frame.crs is None or "PFBAS_ID" not in frame.columns:
            raise ApiError("BOUNDARY_UNAVAILABLE", 503)
        if frame.crs.is_projected and all(
            a.unit_conversion_factor == 1 for a in frame.crs.axis_info
        ):
            areas = frame.geometry.area / 1e6
        else:
            areas = frame.to_crs("EPSG:6933").geometry.area / 1e6
        frame = frame[["PFBAS_ID", "geometry"]].copy()
        frame["area_km2"] = areas
        frame["PFBAS_ID"] = frame["PFBAS_ID"].astype(str).str.strip()
        frame = frame.to_crs("EPSG:4326")
        # Preserve the original map's display tolerances. Scientific geometry is untouched.
        if level == 10:
            frame.geometry = frame.geometry.simplify(0.002, preserve_topology=True)
        elif level in (12, 14):
            frame.geometry = [
                g.simplify(
                    0.001 if a < 100 else 0.002 if a < 500 else 0.005,
                    preserve_topology=True,
                )
                for g, a in zip(frame.geometry, areas)
            ]
        raw = frame.to_json(
            drop_id=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        folder.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(gzip.compress(raw, compresslevel=1))
        temporary.replace(target)
    return target


def layer_response(level):
    from flask import Response, request, send_file

    target = layer_cache(level)
    if request.accept_encodings["gzip"] > 0:
        # Stream the existing compressed file instead of copying it per visitor.
        response = send_file(target, mimetype="application/json", conditional=True,
                             etag=True, max_age=300)
        response.headers["Content-Encoding"] = "gzip"
    else:
        response = Response(gzip.decompress(target.read_bytes()), mimetype="application/json")
        response.set_etag(target.stem + "-identity")
        response.headers["Cache-Control"] = "public, max-age=300"
        response.make_conditional(request)
    response.headers["Vary"] = "Accept-Encoding"
    return response
