#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
程序一：生成流域掩膜 TIF 及位置信息
支持命令行调用和函数导入
"""

import numpy as np
import rasterio
from rasterio import features
import geopandas as gpd
import json
import argparse


def generate_mask(shp_path, code, field, tif_path, out_mask_path, out_json_path, expand=1, verbose=True):
    """
    生成流域掩膜 TIF 及位置信息
    
    参数:
        shp_path: Shapefile 路径
        code: 流域编码（如 '01010105000000'）
        field: 存储编码的字段名
        tif_path: 模板 GeoTIFF（与 PFB 完全对齐）
        out_mask_path: 输出掩膜 TIF 路径
        out_json_path: 输出位置 JSON 文件路径
        expand: 向外扩展的像素数，默认1
        verbose: 是否打印详细信息，默认 True
    
    返回:
        dict: 位置信息 {'row_min': int, 'col_min': int, 'height': int, 'width': int}
    """
    def log(msg):
        if verbose:
            print(f"[程序一] {msg}")
    
    # 1. 读取流域几何
    gdf = gpd.read_file(shp_path)
    basin = gdf[gdf[field] == code]
    if basin.empty:
        raise ValueError(f"未找到编码 {code} 的记录")
    geom = basin.geometry.unary_union if len(basin) > 1 else basin.geometry.iloc[0]
    shp_crs = gdf.crs

    # 2. 利用模板 TIF 生成掩膜
    with rasterio.open(tif_path) as src:
        # 投影几何到模板的 CRS
        gdf_geom = gpd.GeoDataFrame(geometry=[geom], crs=shp_crs)
        geom_proj = gdf_geom.to_crs(src.crs).geometry.iloc[0]

        # Snap to integer source pixels so the TIFF mask and PFB agree.
        if src.transform.b or src.transform.d or src.transform.a <= 0 or src.transform.e >= 0:
            raise ValueError("模板必须是北向上的规则网格")
        if not isinstance(expand, int) or expand < 0:
            raise ValueError("expand 必须是非负整数")
        from rasterio.features import geometry_window
        from rasterio.windows import Window
        window = geometry_window(src, [geom_proj], pad_x=expand, pad_y=expand)
        col_min, row_min = int(window.col_off), int(window.row_off)
        width, height = int(window.width), int(window.height)
        out_transform = src.window_transform(Window(col_min, row_min, width, height))
        mask_uint8 = features.geometry_mask(
            [geom_proj], out_shape=(height, width), transform=out_transform,
            invert=True, all_touched=False,
        ).astype(np.uint8)
        if not mask_uint8.any():
            raise ValueError("该流域在当前分辨率下没有有效像元")
        profile = src.profile.copy()
        profile.update(driver="GTiff", height=height, width=width,
                       transform=out_transform, dtype=rasterio.uint8,
                       count=1, compress="lzw", nodata=None)
        with rasterio.open(out_mask_path, "w", **profile) as dst:
            dst.write(mask_uint8, 1)
        log(f"掩膜已保存: {out_mask_path}")

        pos_info = {
            "row_min": row_min,
            "col_min": col_min,
            "height": height,
            "width": width
        }
        with open(out_json_path, "w") as f:
            json.dump(pos_info, f, indent=2)
        log(f"位置信息已保存: {out_json_path}")
        log(f"起始行列 (row, col) = ({row_min}, {col_min}), 尺寸 = {height} x {width}")
        
        return pos_info


def main():
    parser = argparse.ArgumentParser(description="生成流域掩膜 TIF 及位置信息")
    parser.add_argument("--shp", required=True, help="Shapefile 路径")
    parser.add_argument("--code", required=True, help="流域编码（如 '123456'）")
    parser.add_argument("--field", default="PFBAS", help="存储编码的字段名，默认 PFBAS")
    parser.add_argument("--tif", required=True, help="与 PFB 完全对齐的模板 GeoTIFF")
    parser.add_argument("--out_mask", required=True, help="输出掩膜 TIF 路径")
    parser.add_argument("--out_json", required=True, help="输出位置 JSON 文件路径")
    parser.add_argument("--expand", type=int, default=1, help="向外扩展的像素数，默认1")
    args = parser.parse_args()

    generate_mask(
        shp_path=args.shp,
        code=args.code,
        field=args.field,
        tif_path=args.tif,
        out_mask_path=args.out_mask,
        out_json_path=args.out_json,
        expand=args.expand,
        verbose=True
    )


if __name__ == "__main__":
    main()