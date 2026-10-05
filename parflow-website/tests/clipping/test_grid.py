"""Scientific checks against independently sampled source pixels."""
import json
from pathlib import Path
import tempfile
import unittest

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box
from parflow.tools.io import write_pfb, read_pfb
from concnshare.generate_mask import generate_mask
from concnshare.crop_pfb import crop_pfb


class GridTests(unittest.TestCase):
    def test_fractional_bounds_snap_and_preserve_values_and_y_orientation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            transform = from_origin(0, 100, 10, 10)
            with rasterio.open(root / 'template.tif', 'w', driver='GTiff', width=10,
                               height=10, count=1, dtype='uint8', crs='EPSG:3857',
                               transform=transform) as out:
                out.write(np.zeros((10, 10), dtype='uint8'), 1)
            shape = box(21, 43, 57, 79)
            gpd.GeoDataFrame({'PFBAS_ID': ['01010101010000']}, geometry=[shape],
                             crs='EPSG:3857').to_file(root / 'basin.shp')
            pos = generate_mask(root / 'basin.shp', '01010101010000', 'PFBAS_ID',
                                root / 'template.tif', root / 'mask.tif',
                                root / 'pos.json', verbose=False)
            with rasterio.open(root / 'mask.tif') as mask_file:
                self.assertEqual(mask_file.transform,
                                 transform * rasterio.Affine.translation(pos['col_min'], pos['row_min']))
                mask = mask_file.read(1)
                for row in range(mask.shape[0]):
                    for col in range(mask.shape[1]):
                        from shapely.geometry import Point
                        self.assertEqual(bool(mask[row, col]), shape.contains(Point(*mask_file.xy(row, col))))
            source = np.arange(200, dtype=float).reshape(2, 10, 10) + 1
            write_pfb(str(root / 'source.pfb'), source, dist=False)
            actual = crop_pfb(str(root / 'source.pfb'), root / 'mask.tif', root / 'pos.json',
                              str(root / 'out.pfb'), verbose=False)
            for y in range(pos['height']):
                for x in range(pos['width']):
                    original_y = 10 - pos['row_min'] - pos['height'] + y
                    expected = source[:, original_y, pos['col_min'] + x] if mask[-1-y, x] else np.zeros(2)
                    np.testing.assert_array_equal(actual[:, y, x], expected)
            np.testing.assert_array_equal(read_pfb(str(root / 'out.pfb')), actual)
            bad = dict(pos, col_min=-1)
            (root / 'pos.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                crop_pfb(str(root / 'source.pfb'), root / 'mask.tif', root / 'pos.json',
                         str(root / 'bad.pfb'), verbose=False)
