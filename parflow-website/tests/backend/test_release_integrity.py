from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from concnshare.config import ClipConfig
from datahub.workers.clip import build

BASIN_CODE = '03030109050100'
PFBAS_LEVEL = 12


def fixture(root):
    cfg = ClipConfig(input_pfb_dir=root, shp_dir=root, tif_dir=root,
                     pfmask_cmd=root / 'converter')
    files = []
    for name in cfg.pfb_inputs:
        (root / name).write_bytes(b'known-source')
        files.append(dict(file_kind='source', storage_key=name,
                          source_sha256=hashlib.sha256(b'known-source').hexdigest()))
    assets = []
    for kind, suffix in (('shp', 'shp'), ('tif', 'tif')):
        name = f'PFBAS{PFBAS_LEVEL}.{suffix}'
        (root / name).write_bytes(b'boundary')
        assets.append(dict(kind=kind, name=name,
                           sha256=hashlib.sha256(b'boundary').hexdigest()))
    cfg.pfmask_cmd.write_bytes(b'installed-converter')
    grid = dict(source_assets=assets, pfmask_sha256='old-converter-digest',
                pipeline_sha256={'config.py': 'old-script-digest'})
    snapshot = dict(files=files, grid=grid, pfbas_level=PFBAS_LEVEL,
                    basin_code=BASIN_CODE, version_code='concn1.1')
    return cfg, snapshot


class ReleaseIntegrityTests(unittest.TestCase):
    def test_changed_scientific_inputs_are_rejected(self):
        for changed in ('source', 'shp', 'tif'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                cfg, snapshot = fixture(root)
                name = cfg.pfb_inputs[0] if changed == 'source' else f'PFBAS{PFBAS_LEVEL}.{changed}'
                (root / name).write_bytes(b'changed')
                message = 'Source digest mismatch' if changed == 'source' else 'Boundary/template digest mismatch'
                with patch('datahub.workers.clip.ClipConfig', return_value=cfg), \
                     patch('datahub.workers.clip.run_basin_clip') as clip:
                    with self.assertRaisesRegex(ValueError, message):
                        build(snapshot, root)
                    clip.assert_not_called()
                self.assertFalse((root / 'result.zip').exists())

    def test_old_tool_digests_allow_current_tool_and_preserve_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cfg, snapshot = fixture(root)
            with patch('datahub.workers.clip.ClipConfig', return_value=cfg), \
                 patch('datahub.workers.clip.run_basin_clip', side_effect=RuntimeError('tool failed')) as clip:
                with self.assertRaisesRegex(RuntimeError, 'tool failed'):
                    build(snapshot, root)
                clip.assert_called_once_with(BASIN_CODE, root / 'outputs', config=replace(cfg, data_version=snapshot['version_code']))
            self.assertFalse((root / 'result.zip').exists())
