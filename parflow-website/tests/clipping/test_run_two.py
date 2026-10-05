import os
from pathlib import Path
import unittest
from unittest.mock import patch

from concnshare.config import ClipConfig
from concnshare.run_two import (
    get_output_filename,
    get_pfbas_level,
    validate_basin_code,
)


class BasinCodeTests(unittest.TestCase):
    def test_validate_basin_code(self):
        self.assertEqual(validate_basin_code(" 01020300000000 "), "01020300000000")
        for invalid in ("", "123", "0102030000000x", "010203000000000"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_basin_code(invalid)

    def test_get_pfbas_level(self):
        cases = {
            "01000000000000": 2,
            "01020000000000": 4,
            "01020300000000": 6,
            "01020301000000": 8,
            "01020301040500": 12,
            "01020301040506": 14,
        }
        for code, expected in cases.items():
            with self.subTest(code=code):
                self.assertEqual(get_pfbas_level(code), expected)

    def test_output_filename_uses_public_names(self):
        code = "01020300000000"
        self.assertEqual(
            get_output_filename("/data/CONCN_manning.fix.2026.pfb", code),
            f"manning.{code}.pfb",
        )
        with self.assertRaises(ValueError):
            get_output_filename("unknown.pfb", code)


class ConfigTests(unittest.TestCase):
    def test_cluster_paths_can_be_overridden(self):
        with patch.dict(os.environ, {"CONCN_SHP_DIR": "/tmp/test-shp"}):
            config = ClipConfig()
        self.assertEqual(config.shp_dir, Path("/tmp/test-shp"))


if __name__ == "__main__":
    unittest.main()
