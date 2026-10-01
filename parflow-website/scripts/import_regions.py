"""Cache public GeoAtlas navigation data, then import province/city locations.

Run migration 002 first. This stores navigation extents only, never clipping boundaries.
Municipalities and SARs use the same region as their city-level navigation choice.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from datahub.repositories.db import transaction

BASE = 'https://geo.datav.aliyun.com/areas_v3/bound/'
CACHE = ROOT / '.local/regions'


def fetch(code):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f'{code}_full.json'
    if not path.exists():
        with urlopen(BASE + path.name, timeout=60) as response:
            payload = response.read()
        json.loads(payload)
        path.write_bytes(payload)
    return json.loads(path.read_text(encoding='utf-8'))


def record(feature, kind, parent, url):
    from shapely.geometry import shape
    props = feature['properties']
    code = str(props['adcode'])
    if not code.isdigit() or len(code) != 6:
        raise ValueError('Invalid administrative code')
    bounds = list(shape(feature['geometry']).bounds)
    center = props.get('centroid') or props['center']
    return (code, kind, parent, props['name'], *center, json.dumps(bounds), url)


def main():
    provinces = [f for f in fetch('100000')['features'] if f['properties'].get('level') == 'province']
    municipal = {'110000','120000','310000','500000','810000','820000'}
    normal = [str(f['properties']['adcode']) for f in provinces
              if str(f['properties']['adcode']) not in municipal and f['properties'].get('childrenNum')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        children = dict(zip(normal, pool.map(fetch, normal)))
    rows = []
    for province in provinces:
        code = str(province['properties']['adcode'])
        rows.append(record(province, 'province', None, BASE+'100000_full.json'))
        if code in municipal:
            rows.append(record(province, 'city', code, BASE+'100000_full.json'))
        elif code in children:
            for feature in children[code]['features']:
                if not feature['properties'].get('name'):
                    continue
                if str(feature['properties'].get('parent',{}).get('adcode')) != code:
                    raise ValueError('Unexpected province hierarchy')
                rows.append(record(feature, 'city', code, BASE+code+'_full.json'))
    with transaction() as c:
        c.executemany('''INSERT INTO administrative_regions(code,kind,parent_code,name_zh,center_lng,center_lat,view_bounds,source_url)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE name_zh=VALUES(name_zh),center_lng=VALUES(center_lng),center_lat=VALUES(center_lat),view_bounds=VALUES(view_bounds),source_url=VALUES(source_url),imported_at=CURRENT_TIMESTAMP''', rows)
    print(f'Imported {len(provinces)} provinces and {len(rows)-len(provinces)} city/area navigation entries.')


if __name__ == '__main__':
    main()
