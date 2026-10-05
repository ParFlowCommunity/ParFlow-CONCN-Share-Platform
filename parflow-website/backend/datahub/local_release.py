"""Validate and publish the user's local inputs for local website acceptance.

No fabricated geography, destructive catalog replacement, or public deployment.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

from .config import ROOT
from .repositories.db import transaction, one, dump

sys.path.insert(0, str(ROOT))
from concnshare.config import ClipConfig
from concnshare.run_two import OUTPUT_NAMES, get_pfbas_level

VERSION = "concn1.1"
# Preserve the signed source manifest identity when renaming the existing release.
MANIFEST_VERSION = "CONCN-local-2026.09-grid2"
PIPELINE = ("config.py", "generate_mask.py", "crop_pfb.py", "run_two.py")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare():
    import geopandas as gpd
    import numpy as np
    import rasterio
    from parflow.tools.io import ParflowBinaryReader
    from rasterio.features import geometry_mask, geometry_window

    cfg = ClipConfig()
    if not cfg.pfmask_cmd.is_file():
        raise ValueError("Missing pfmask-to-pfsol")
    files, assets, basins = [], [], []
    grid = {k: getattr(cfg, k) for k in ("dx", "dy", "dz", "expand", "z_top", "z_bottom",
                                      "bottom_patch_label", "side_patch_label")}
    dimensions = None
    for name in cfg.pfb_inputs:
        path = cfg.input_pfb_dir / name
        with ParflowBinaryReader(str(path)) as reader:
            header = reader.header
            xy = (header['nx'], header['ny'])
            if dimensions and dimensions != xy:
                raise ValueError("Source PFB horizontal dimensions differ")
            dimensions = xy
            expected_z = 10 if OUTPUT_NAMES[name] in ('bedrock', 'subsurface') else 1
            if header['nz'] != expected_z:
                raise ValueError("Unexpected input vertical layers")
        files.append(dict(item_code=OUTPUT_NAMES[name], file_kind="source", storage_key=name,
                          source_sha256=sha256(path), output_name_template=OUTPUT_NAMES[name]+".{basin_code}.pfb",
                          metadata={"layers": expected_z, "source_bytes": path.stat().st_size}))
    seen = set()
    for level in range(2, 15, 2):
        for extension in ("shp", "shx", "dbf", "prj", "cpg"):
            path = cfg.shp_dir / f"PFBAS{level}.{extension}"
            assets.append(dict(kind="shp", name=path.name, sha256=sha256(path)))
        template = cfg.tif_dir / f"PFBAS{level}.tif"
        assets.append(dict(kind="tif", name=template.name, sha256=sha256(template)))
        gdf = gpd.read_file(cfg.shp_dir / f"PFBAS{level}.shp")
        if gdf.crs is None or gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
            raise ValueError("Missing boundary geometry/CRS")
        geographic = gdf.to_crs(4326)
        area = gdf.to_crs(6933).area / 1e6
        centers = geographic.geometry.representative_point()
        with rasterio.open(template) as src:
            if (src.width, src.height) != dimensions or src.crs is None:
                raise ValueError("Template and PFB dimensions differ")
            if src.transform.b or src.transform.d or src.transform.a <= 0 or src.transform.e >= 0:
                raise ValueError("Unsupported template grid")
            if not np.isclose(src.transform.a, cfg.dx, rtol=1e-5) or not np.isclose(-src.transform.e, cfg.dy, rtol=1e-5):
                raise ValueError("Unexpected grid spacing")
            projected = gdf.to_crs(src.crs)
            for index, row in gdf.iterrows():
                code = str(row.PFBAS_ID)
                if code in seen or get_pfbas_level(code) != level:
                    raise ValueError("Duplicate or invalid basin hierarchy")
                parent = code[:level-2].ljust(14, "0") if level > 2 else None
                if parent and parent not in seen:
                    raise ValueError("Missing parent basin")
                seen.add(code)
                geom = projected.geometry.loc[index]
                reason = None
                peak = None
                try:
                    if not geom.is_valid:
                        raise ValueError("invalid geometry")
                    win = geometry_window(src, [geom], pad_x=cfg.expand, pad_y=cfg.expand)
                    height, width = int(win.height), int(win.width)
                    # A center-sampled mask is the same criterion used by the clipper.
                    mask = geometry_mask([geom], (height, width), src.window_transform(win), invert=True)
                    if not mask.any():
                        raise ValueError("no cells")
                    peak = width * height * 8 * 35
                except (ValueError, rasterio.errors.WindowError):
                    reason = "边界无有效网格或几何待修复 / No valid grid cells or invalid geometry"
                bounds = geographic.geometry.loc[index].bounds
                center = centers.loc[index]
                basins.append(dict(basin_code=code, pfbas_level=level, parent_code=parent,
                                   name_zh=f"流域 {code}", name_en=f"Basin {code}",
                                   area_km2=float(area.loc[index]), center_lng=center.x,
                                   center_lat=center.y, bbox_wgs84=list(bounds),
                                   available=reason is None, reason=reason, peak=peak))
        print(f"Validated PFBAS{level}: {len(gdf)} basins", flush=True)
    grid["source_assets"] = assets
    grid["pipeline_sha256"] = {name: sha256(ROOT / "concnshare" / name) for name in PIPELINE}
    grid["pfmask_sha256"] = sha256(cfg.pfmask_cmd)
    for item, template in (("mask_tif", "mask.{basin_code}.tif"), ("mask_pfb", "mask.{basin_code}.pfb"),
                           ("vtk", "{basin_code}.vtk"), ("pfsol", "{basin_code}.pfsol"),
                           ("metadata", "metadata.json"), ("readme", "README.txt"),
                           ("citation", "CITATION.txt"), ("checksums", "SHA256SUMS.txt")):
        files.append(dict(item_code=item, file_kind="generated", storage_key="recipe:"+item,
                          source_sha256=None, output_name_template=template, metadata=None))
    payload = dict(version=MANIFEST_VERSION, grid=grid, files=files, basins=basins)
    payload["manifest_sha256"] = hashlib.sha256(dump(payload).encode()).hexdigest()
    return payload


def publish_local():
    if os.getenv("CONCN_ENV") != "development" or os.getenv("MYSQL_HOST", "127.0.0.1") not in ("127.0.0.1", "localhost"):
        raise ValueError("This command is restricted to local development")
    release = prepare()
    citation = "Yang C et al. (2025). CONCN: a high-resolution, integrated surface water-groundwater ParFlow modeling platform of continental China. Hydrology and Earth System Sciences, 29, 2201–2218."
    with transaction() as c:
        one(c, "SELECT id FROM platform_config WHERE id=1 FOR UPDATE")
        existing = one(c, "SELECT id,manifest_sha256 FROM dataset_versions WHERE version_code=%s", (VERSION,))
        if existing:
            if existing['manifest_sha256'].hex() != release['manifest_sha256']:
                raise ValueError("Existing release differs; use a new version code, never overwrite")
            print(f"Identical release already present: {existing['id']}")
            return existing['id']
        for b in release['basins']:
            existing = one(c, "SELECT pfbas_level,parent_code FROM watersheds WHERE basin_code=%s", (b['basin_code'],))
            if existing:
                if existing['pfbas_level'] != b['pfbas_level'] or existing['parent_code'] != b['parent_code']:
                    raise ValueError("Existing catalog hierarchy differs")
                continue
            c.execute("INSERT INTO watersheds(basin_code,pfbas_level,parent_code,name_zh,name_en,area_km2,center_lng,center_lat,bbox_wgs84,status) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'available')",
                      tuple(b[k] for k in ('basin_code','pfbas_level','parent_code','name_zh','name_en','area_km2','center_lng','center_lat'))+(dump(b['bbox_wgs84']),))
        c.execute("""INSERT INTO dataset_versions(version_code,title_zh,title_en,description_zh,description_en,status,boundary_version,clip_version,manifest_sha256,grid_metadata,citation,terms_version,license_text_zh,license_text_en,published_at)
                     VALUES(%s,%s,%s,%s,%s,'published',%s,%s,%s,%s,%s,%s,%s,%s,UTC_TIMESTAMP(6))""",
                  (VERSION, VERSION, VERSION,
                   "完整基础输入包：五类 PFB、掩膜、PFSOL、VTK 和说明。额外 CLM 参数、气象驱动及完整模拟脚本不在本版裁切范围内。",
                   "Full base-input package: five PFB inputs, masks, PFSOL, VTK and documentation. Additional CLM parameters, meteorological forcing and simulation scripts are outside this release.",
                   "local-PFBAS-7-levels", "aligned-grid-v2", bytes.fromhex(release['manifest_sha256']), dump(release['grid']), citation,
                   "local-validation-v1", "本地流程验证版本。科研使用请核对数据适用性并按 CITATION.txt 引用；公网数据许可由平台管理员后续配置。",
                   "Local workflow validation release. Verify scientific suitability and cite CITATION.txt. Public data licensing is to be configured by the platform administrator."))
        version = c.lastrowid
        c.executemany("INSERT INTO dataset_files(dataset_version_id,item_code,title_zh,title_en,storage_key,file_kind,source_sha256,output_name_template,metadata) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                      [(version, f['item_code'], f['item_code'], f['item_code'], f['storage_key'], f['file_kind'], bytes.fromhex(f['source_sha256']) if f['source_sha256'] else None,
                        f['output_name_template'], dump(f['metadata'])) for f in release['files']])
        c.executemany("INSERT INTO watershed_datasets(basin_code,dataset_version_id,status,unavailable_reason_zh,unavailable_reason_en,estimated_peak_memory_bytes) VALUES(%s,%s,%s,%s,%s,%s)",
                      [(b['basin_code'], version, 'available' if b['available'] else 'unavailable', b['reason'], b['reason'], b['peak']) for b in release['basins']])
    folder = ROOT / '.local/releases'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (VERSION+'.json')).write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Local release {version}: {len(release['basins'])} basins; {sum(b['available'] for b in release['basins'])} downloadable", flush=True)
    return version
