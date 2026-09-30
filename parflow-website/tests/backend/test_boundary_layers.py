"""Original map's read-only boundary adapter; never imports data into MySQL."""

import gzip
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from datahub.integrations import boundary_layers
from datahub.web import create_app


class OriginalMapTests(unittest.TestCase):
    def test_level_validation_does_not_read_arbitrary_paths(self):
        client = create_app(testing=True).test_client()
        with patch.object(boundary_layers, "layer_cache") as load:
            for level in ("1", "3", "16", "../2", "2 OR 1=1"):
                self.assertEqual(
                    client.get(
                        "/api/boundaries", query_string={"level": level}
                    ).status_code,
                    400,
                )
            load.assert_not_called()

    def test_level_geojson_cache_and_gzip_do_not_publish_datasets(self):
        try:
            import geopandas as gpd
            from shapely.geometry import box
        except ImportError:
            self.skipTest("Map data dependencies are not installed")
        with TemporaryDirectory(prefix="concn-map-test-") as directory:
            root = Path(directory)
            frame = gpd.GeoDataFrame(
                {"PFBAS_ID": ["01000000000000"]},
                geometry=[box(0, 0, 1000, 1000)],
                crs="EPSG:3857",
            )
            frame.to_file(root / "PFBAS2.shp")
            with (
                patch.dict(os.environ, {"CONCN_SHP_DIR": str(root)}),
                patch.object(boundary_layers, "BACKEND", root),
            ):
                client = create_app(testing=True).test_client()
                plain = client.get("/api/boundaries?level=2")
                self.assertEqual(plain.status_code, 200)
                self.assertEqual(
                    plain.get_json()["features"][0]["properties"]["PFBAS_ID"],
                    "01000000000000",
                )
                self.assertEqual(
                    plain.get_json()["features"][0]["properties"]["area_km2"], 1
                )
                with patch(
                    "geopandas.read_file",
                    side_effect=AssertionError("Cache should be used"),
                ):
                    zipped = client.get(
                        "/api/boundaries?level=2", headers={"Accept-Encoding": "gzip"}
                    )
                self.assertEqual(zipped.headers["Content-Encoding"], "gzip")
                self.assertEqual(
                    json.loads(gzip.decompress(zipped.data)), plain.get_json()
                )
                self.assertIn("max-age=300", zipped.headers["Cache-Control"])
                etag = zipped.headers["ETag"]
                zipped.close()
                unchanged = client.get("/api/boundaries?level=2", headers={
                    "Accept-Encoding": "gzip", "If-None-Match": etag,
                })
                self.assertEqual(unchanged.status_code, 304)
                self.assertEqual(unchanged.data, b"")
                unchanged.close()
                refused = client.get("/api/boundaries?level=2", headers={
                    "Accept-Encoding": "gzip;q=0",
                })
                self.assertNotIn("Content-Encoding", refused.headers)
                self.assertEqual(refused.get_json(), plain.get_json())
                self.assertEqual(client.get("/api/boundaries?level=3").headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
