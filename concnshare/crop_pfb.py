# crop_pfb.py 修正版
import json
import argparse

def crop_pfb(
    pfb_path,
    mask_path,
    pos_json_path,
    out_pfb_path,
    verbose=True,
    dx=961.72,
    dy=961.72,
    dz=200.0,
):
    import numpy as np
    import rasterio
    from parflow.tools.io import ParflowBinaryReader, write_pfb

    def log(msg):
        if verbose:
            print(f"[程序二] {msg}")
    
    with open(pos_json_path, "r") as f:
        pos = json.load(f)
    row_min = pos["row_min"]
    col_min = pos["col_min"]
    height = pos["height"]
    width = pos["width"]
    log(f"位置信息: 起始行={row_min}, 起始列={col_min}, 尺寸={height}x{width}")

    with rasterio.open(mask_path) as src:
        mask = src.read(1)
        mask = (mask > 0).astype(np.uint8)
    if mask.shape != (height, width):
        raise ValueError("掩膜尺寸与位置记录不一致")

    log(f"读取 PFB 窗口: {pfb_path}")
    with ParflowBinaryReader(pfb_path) as reader:
        ny, nx = reader.header["ny"], reader.header["nx"]
        if min(row_min, col_min) < 0 or row_min + height > ny or col_min + width > nx:
            raise ValueError("裁剪区域超出 PFB 范围")
        # TIFF is north-to-south; PFB stores y south-to-north.
        pfb_cropped = reader.read_subarray(col_min, ny - row_min - height, 0,
                                          width, height, reader.header["nz"])
    pfb_result = np.where(mask[np.newaxis, ::-1, :] > 0, pfb_cropped, 0.0)

    # 确保输出为 float64
    pfb_result = pfb_result.astype(np.float64, copy=False)
    write_pfb(out_pfb_path, pfb_result, dx=dx, dy=dy, dz=dz, dist=False)
    log(f"裁剪后 PFB 已保存: {out_pfb_path}")
    log(f"输出形状: {pfb_result.shape}")
    log(f"非零像素数（流域内）: {np.sum(pfb_result != 0)}")
    return pfb_result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pfb", required=True)
    parser.add_argument("--mask", required=True)
    parser.add_argument("--pos_json", required=True)
    parser.add_argument("--out_pfb", required=True)
    args = parser.parse_args()
    crop_pfb(args.pfb, args.mask, args.pos_json, args.out_pfb, verbose=True)

if __name__ == "__main__":
    main()
