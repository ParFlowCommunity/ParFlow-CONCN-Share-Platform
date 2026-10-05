import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from datahub.workers import clip
from datahub.package_content import public_metadata


class PackageTests(unittest.TestCase):
    def test_public_levels(self):
        for level in range(2, 15, 2):
            result = public_metadata({'pfbas_level': level, 'boundary_version': 'old'})
            self.assertEqual(result['pfbas_level'], level // 2)
            self.assertEqual(result['concn_data_version'], 'concn1.1')
            self.assertNotIn('boundary_version', result)

    def test_zip_content(self):
        code = '01010101010100'
        with TemporaryDirectory() as directory:
            work = Path(directory)
            folder = work / 'outputs' / code
            folder.mkdir(parents=True)
            names = [f'{v}.{code}.pfb' for v in ('slopex','slopey','bedrock','manning','subsurface','mask')]
            names += [f'mask.{code}.tif', f'{code}.pfsol', f'{code}.vtk']
            for name in names:
                (folder / name).write_bytes(b'synthetic packaging fixture')
            (folder / 'metadata.json').write_text(json.dumps({'pfbas_level':12,'concn_data_version':'internal','grid':{'dx':961.72}}))
            # 流水线自带的说明文本一律不进下载包；CITATION.txt 由平台按数据版本重写。
            excluded = ['SHA256SUMS.txt', 'README.txt', 'readme.txt']
            # 小写 citation.txt 是流水线可能留下的旧写法：清单里不声明它，只验证它会被清掉。
            for name in excluded + ['CITATION.txt', 'citation.txt']:
                (folder / name).write_text('legacy')
            snapshot = {'files':[{'file_kind':'generated','output_name_template':name} for name in names + ['metadata.json'] + excluded + ['CITATION.txt']],
                        'grid':{}, 'version_code':'internal', 'basin_code':code,
                        'citation':'Yang C et al. (2025). CONCN. Hydrology and Earth System Sciences, 29, 2201-2218.'}
            from dataclasses import replace
            cfg = replace(clip.ClipConfig(), pfb_inputs=())
            with patch.object(clip, 'ClipConfig', return_value=cfg), patch.object(clip, 'run_basin_clip', return_value=folder):
                clip.build(snapshot, work)
            with zipfile.ZipFile(work / 'result.zip') as z:
                self.assertEqual(len(z.namelist()), 11)
                for name in excluded:
                    self.assertNotIn(code + '/' + name, z.namelist())
                # 平台生成的引用文件生效，流水线自带的旧版本被替换掉。
                self.assertNotIn(code + '/citation.txt', z.namelist())
                citation = z.read(code + '/CITATION.txt').decode('utf-8')
                self.assertIn('Hydrology and Earth System Sciences', citation)
                self.assertIn('Basin code: ' + code, citation)
                metadata = json.loads(z.read(code + '/metadata.json'))
                self.assertEqual(metadata['pfbas_level'], 6)
                self.assertEqual(metadata['concn_data_version'], 'concn1.1')
                self.assertFalse(set(metadata) & {'boundary_version','clip_version','source_manifest_sha256','package_mode'})
            result = json.loads((work / 'result.json').read_text())
            self.assertTrue(result['sha256'])
            self.assertEqual(len(result['files']), 11)
