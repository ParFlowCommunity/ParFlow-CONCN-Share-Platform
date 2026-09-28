"""Read a single authoritative basin geometry. No country-wide full layer download."""

from pathlib import Path
import json
import os
import re
from ..common import ApiError


def get_boundary(code, level):
    if not re.fullmatch("[0-9]{14}", code) or level not in range(2, 15, 2):
        raise ApiError("INVALID_INPUT")
    path = (
        Path(
            os.getenv(
                "CONCN_SHP_DIR",
                "/data/share/parflow-group/CONCN_Subbasins_Map/PFBAS/shp",
            )
        )
        / f"PFBAS{level}.shp"
    )
    if not path.is_file():
        raise ApiError("BOUNDARY_UNAVAILABLE", 503)
    try:
        import geopandas as gpd
    except ImportError:
        raise ApiError("BOUNDARY_UNAVAILABLE", 503)
    frame = gpd.read_file(path, where=f"PFBAS_ID = '{code}'")
    if frame.empty or frame.crs is None:
        raise ApiError("BOUNDARY_UNAVAILABLE", 503)
    frame = frame.to_crs("EPSG:4326")
    # Display-only simplification. Original geometry remains the clipping source.
    frame.geometry = frame.geometry.simplify(0.001, preserve_topology=True)
    return json.loads(frame[["PFBAS_ID", "geometry"]].to_json())
