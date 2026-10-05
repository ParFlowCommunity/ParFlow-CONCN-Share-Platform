"""Stable repository paths and local environment loading."""

import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"
load_dotenv(BACKEND / ".env")

DEFAULT_SHP_DIR = Path("/data/share/parflow-group/CONCN_Subbasins_Map/PFBAS/shp")


def shp_dir():
    """PFBAS Shapefile 目录。

    两个边界模块共用这一个取值，避免同一份配置在“单流域边界”和“分级图层”两条
    路径上解析出不同结果。空字符串同样按未配置处理，否则会解析成相对路径。
    """
    return Path(os.getenv("CONCN_SHP_DIR") or DEFAULT_SHP_DIR)
