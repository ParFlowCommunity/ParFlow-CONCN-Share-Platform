#!/usr/bin/env python
"""生成流域掩膜、域文件并裁剪 CONCN PFB 输入。"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from .config import ClipConfig


OUTPUT_NAMES = {
    "CHN.slopex.2026.fix.pfb": "slopex",
    "CHN.slopey.2026.fix.pfb": "slopey",
    "Shangguan_300m_FBZ_fix.pfb": "bedrock",
    "CONCN_manning.fix.2026.pfb": "manning",
    "GLHYMPS1.0_multi_efold_fix.pfb": "subsurface",
}


def validate_basin_code(basin_code):
    """校验并返回规范化后的 14 位流域编码。"""
    code = str(basin_code).strip()
    if len(code) != 14 or not code.isdigit():
        raise ValueError(f"流域编码必须是14位数字，实际为: {code!r}")
    return code


def get_output_filename(input_filename, basin_code):
    code = validate_basin_code(basin_code)
    base_name = Path(input_filename).name
    try:
        core_name = OUTPUT_NAMES[base_name]
    except KeyError as exc:
        raise ValueError(f"未定义输出映射规则的文件: {base_name}") from exc
    return f"{core_name}.{code}.pfb"


def get_pfbas_level(pfbas_code):
    """根据固定 14 位、两位一级的编码推断 PFBAS 级别。"""
    code = validate_basin_code(pfbas_code)
    effective_length = len(code.rstrip("0"))
    if effective_length <= 2:
        return 2
    return min(14, effective_length + effective_length % 2)


def _require_file(path, description):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"{description}不存在: {path}")
    return path


def convert_mask_tif_to_pfb(mask_tif_path, mask_pfb_path, config=None):
    """将 GeoTIFF 掩膜转换为单层 PFB，保持流域内 1、流域外 0。"""
    import numpy as np
    import rasterio
    from parflow.tools.io import write_pfb

    config = config or ClipConfig()
    with rasterio.open(mask_tif_path) as src:
        mask_2d = src.read(1).astype(np.uint8)
    mask_3d = mask_2d[np.newaxis, ::-1, :].astype(np.float64, order="C", copy=True)
    write_pfb(
        str(mask_pfb_path),
        mask_3d,
        dx=config.dx,
        dy=config.dy,
        dz=config.dz,
        dist=False,
    )


def generate_domain_files(mask_pfb_path, vtk_path, pfsol_path, output_dir, config=None):
    """调用 ParFlow 的 pfmask-to-pfsol 生成 VTK 和 PFSOL。"""
    config = config or ClipConfig()
    _require_file(config.pfmask_cmd, "pfmask-to-pfsol 可执行文件")
    cmd = [
        str(config.pfmask_cmd),
        "--mask", os.path.relpath(mask_pfb_path, output_dir),
        "--vtk", os.path.relpath(vtk_path, output_dir),
        "--pfsol", os.path.relpath(pfsol_path, output_dir),
        "--bottom-patch-label", str(config.bottom_patch_label),
        "--side-patch-label", str(config.side_patch_label),
        "--z-top", str(config.z_top),
        "--z-bottom", str(config.z_bottom),
    ]
    subprocess.run(
        cmd,
        check=True,
        cwd=str(output_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run_basin_clip(basin_code, base_output_dir, config=None, overwrite=False, verbose=True):
    """运行一个流域的完整裁剪流程并返回输出目录。"""
    from .crop_pfb import crop_pfb
    from .generate_mask import generate_mask

    config = config or ClipConfig()
    code = validate_basin_code(basin_code)
    base_output_dir = Path(base_output_dir).resolve()
    output_dir = base_output_dir / code

    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"输出目录已存在，拒绝覆盖: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    input_paths = [
        _require_file(config.input_pfb_dir / name, "输入 PFB 文件")
        for name in config.pfb_inputs
    ]
    level = get_pfbas_level(code)
    shp_path = _require_file(config.shp_dir / f"PFBAS{level}.shp", "Shapefile")
    tif_template = _require_file(config.tif_dir / f"PFBAS{level}.tif", "模板 GeoTIFF")

    mask_tif = output_dir / f"mask.{code}.tif"
    mask_pfb = output_dir / f"mask.{code}.pfb"
    pos_json = output_dir / "pos.json"
    out_vtk = output_dir / f"{code}.vtk"
    out_pfsol = output_dir / f"{code}.pfsol"

    if verbose:
        print(f"[信息] 流域编码: {code}，级别: PFBAS{level}")
        print(f"[信息] 输出目录: {output_dir}")

    generate_mask(
        shp_path=str(shp_path),
        code=code,
        field=config.field_name,
        tif_path=str(tif_template),
        out_mask_path=str(mask_tif),
        out_json_path=str(pos_json),
        expand=config.expand,
        verbose=verbose,
    )
    convert_mask_tif_to_pfb(mask_tif, mask_pfb, config)
    generate_domain_files(mask_pfb, out_vtk, out_pfsol, output_dir, config)

    cropped_files = []
    for input_path in input_paths:
        output_path = output_dir / get_output_filename(input_path.name, code)
        crop_pfb(
            pfb_path=str(input_path),
            mask_path=str(mask_tif),
            pos_json_path=str(pos_json),
            out_pfb_path=str(output_path),
            verbose=verbose,
            dx=config.dx,
            dy=config.dy,
            dz=config.dz,
        )
        cropped_files.append(output_path.name)

    for dist_file in output_dir.glob("*.dist"):
        dist_file.unlink()
    pos_json.unlink(missing_ok=True)

    metadata = {
        "basin_code": code,
        "pfbas_level": level,
        "concn_data_version": config.data_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "grid": {"dx": config.dx, "dy": config.dy, "dz": config.dz},
        "files": {
            "mask_tif": mask_tif.name,
            "mask_pfb": mask_pfb.name,
            "vtk": out_vtk.name,
            "pfsol": out_pfsol.name,
            "cropped_pfb": cropped_files,
        },
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_dir


def build_parser():
    parser = argparse.ArgumentParser(description="裁剪指定 CONCN 流域的 ParFlow 输入")
    parser.add_argument("basin_code", nargs="?", help="14位流域编码")
    parser.add_argument(
        "--output-dir",
        default=os.getenv("OUTPUT_DIR", str(Path.cwd() / "outputs")),
        help="输出基础目录，默认 $OUTPUT_DIR 或 ./outputs",
    )
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有流域输出目录")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    code = args.basin_code or input("请输入14位流域编码（如01010105000000）: ").strip()
    try:
        output_dir = run_basin_clip(code, args.output_dir, overwrite=args.overwrite)
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        raise SystemExit(f"错误：{exc}") from exc
    print(f"\n=== 全部完成 ===\n输出目录: {output_dir}")


if __name__ == "__main__":
    main()
