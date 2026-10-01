"""CONCN 裁剪流程的集中配置。"""

from dataclasses import dataclass, field
import os
from pathlib import Path


DEFAULT_PFB_INPUTS = (
    "CHN.slopex.2026.fix.pfb",
    "CHN.slopey.2026.fix.pfb",
    "Shangguan_300m_FBZ_fix.pfb",
    "CONCN_manning.fix.2026.pfb",
    "GLHYMPS1.0_multi_efold_fix.pfb",
)


@dataclass(frozen=True)
class ClipConfig:
    """裁剪所需的数据路径和网格参数。

    默认值仍对应当前集群；每项都可通过环境变量覆盖，便于测试和升级。
    """

    shp_dir: Path = field(
        default_factory=lambda: Path(os.getenv(
            "CONCN_SHP_DIR",
            "/data/share/parflow-group/CONCN_Subbasins_Map/PFBAS/shp",
        ))
    )
    tif_dir: Path = field(
        default_factory=lambda: Path(os.getenv(
            "CONCN_TIF_DIR",
            "/data/share/parflow-group/CONCN_Subbasins_Map/PFBAS/geotiff",
        ))
    )
    input_pfb_dir: Path = field(
        default_factory=lambda: Path(os.getenv(
            "CONCN_INPUT_PFB_DIR",
            "/data/share/parflow-group/CONCN1.1/inputs",
        ))
    )
    pfmask_cmd: Path = field(
        default_factory=lambda: Path(os.getenv(
            "PARFLOW_PFMASK_CMD",
            "/data/software/parflow-gnu13/parflow-3.13.0/bin/pfmask-to-pfsol",
        ))
    )
    field_name: str = "PFBAS_ID"
    expand: int = 1
    dx: float = 961.72
    dy: float = 961.72
    dz: float = 200.0
    bottom_patch_label: int = 2
    side_patch_label: int = 3
    z_top: float = 2000.0
    z_bottom: float = 0.0
    pfb_inputs: tuple[str, ...] = DEFAULT_PFB_INPUTS
    data_version: str = field(
        default_factory=lambda: os.getenv("CONCN_DATA_VERSION", "1.1")
    )
