"""Province/city navigation never alters basin access or dataset selection."""
import os
from pathlib import Path
import unittest

from datahub.repositories.db import transaction
from datahub.web import create_app


class RegionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('MYSQL_DATABASE') != 'concn_datahub_test':
            raise RuntimeError('Only disposable test database is allowed')
        with transaction() as c:
            c.execute((Path(__file__).resolve().parents[2] / 'database/migrations/002_regions.sql').read_text(encoding='utf-8'))
            c.execute('DELETE FROM administrative_regions')
            c.executemany('INSERT INTO administrative_regions(code,kind,parent_code,name_zh,center_lng,center_lat,view_bounds,source_url) VALUES(%s,%s,%s,%s,110,30,%s,%s)', [
                ('330000','province',None,'浙江省','[118,27,123,31]','test'),
                ('330100','city','330000','杭州市','[118,29,121,31]','test'),
                ('350100','city','350000','福州市','[118,25,120,27]','test'),
                ('110000','province',None,'北京市','[115,39,118,42]','test'),
                ('110000','city','110000','北京市','[115,39,118,42]','test'),
            ])
        cls.client = create_app(testing=True).test_client()

    def test_public_lists_filter_province_and_decode_bounds(self):
        provinces = self.client.get('/api/regions').get_json()['items']
        self.assertEqual(len(provinces), 2)
        cities = self.client.get('/api/regions?province=330000').get_json()['items']
        self.assertEqual([c['code'] for c in cities], ['330100'])
        self.assertEqual(cities[0]['view_bounds'], [118,29,121,31])

    def test_municipality_and_empty_child_list(self):
        self.assertEqual(self.client.get('/api/regions?province=110000').get_json()['items'][0]['name_zh'], '北京市')
        self.assertEqual(self.client.get('/api/regions?province=999999').get_json()['items'], [])

    def test_invalid_parent_is_rejected(self):
        for value in ['../x', '330000 OR 1=1', '３３００００']:
            self.assertEqual(self.client.get('/api/regions', query_string={'province':value}).status_code, 400)
