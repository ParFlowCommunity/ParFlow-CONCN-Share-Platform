"""Clip with the installed tools while verifying published scientific inputs."""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from ..config import ROOT
from ..package_content import EXCLUDED_PACKAGE_FILES, public_metadata

sys.path.insert(0, str(ROOT))
from concnshare.config import ClipConfig
from concnshare.run_two import run_basin_clip

HASH_BLOCK_BYTES = 1024 * 1024
GRID_PARAMETERS = (
    "dx", "dy", "dz", "expand", "z_top", "z_bottom",
    "bottom_patch_label", "side_patch_label",
)


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(HASH_BLOCK_BYTES), b""):
            h.update(block)
    return h.hexdigest()


def validate_inputs(snapshot, cfg):
    sources = [item for item in snapshot["files"] if item["file_kind"] == "source"]
    if {Path(item["storage_key"]).name for item in sources} != set(cfg.pfb_inputs):
        raise ValueError("Source manifest does not match the full clipping pipeline")
    for source in sources:
        path = cfg.input_pfb_dir / Path(source["storage_key"]).name
        if not source.get("source_sha256") or file_hash(path) != source["source_sha256"]:
            raise ValueError("Source digest mismatch")
    for asset in snapshot["grid"].get("source_assets", []):
        # Only the selected basin's level is used by this clipping task.
        if Path(asset["name"]).stem != f"PFBAS{snapshot['pfbas_level']}":
            continue
        folder = cfg.shp_dir if asset["kind"] == "shp" else cfg.tif_dir
        if file_hash(folder / Path(asset["name"]).name) != asset["sha256"]:
            raise ValueError("Boundary/template digest mismatch")


def prepare_package(folder):
    metadata_path = folder / "metadata.json"
    metadata = public_metadata(json.loads(metadata_path.read_text(encoding="utf-8")))
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for file in folder.iterdir():
        if file.is_file() and file.name.lower() in EXCLUDED_PACKAGE_FILES:
            file.unlink()
    return [
        {"name": file.name, "bytes": file.stat().st_size, "sha256": file_hash(file)}
        for file in sorted(folder.iterdir()) if file.is_file()
    ]


def write_archive(snapshot, folder, workdir):
    manifest = prepare_package(folder)
    expected = {
        item["output_name_template"].replace("{basin_code}", snapshot["basin_code"])
        for item in snapshot["files"]
        if item["output_name_template"].lower() not in EXCLUDED_PACKAGE_FILES
    }
    if not expected.issubset({item["name"] for item in manifest}):
        raise ValueError("Incomplete output package")
    archive = workdir / "result.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as output:
        for item in manifest:
            output.write(folder / item["name"], arcname=f"{snapshot['basin_code']}/{item['name']}")
    result = {
        "byte_size": archive.stat().st_size,
        "sha256": file_hash(archive),
        "files": manifest,
    }
    (workdir / "result.json").write_text(json.dumps(result), encoding="utf-8")


def build(snapshot, workdir):
    cfg = ClipConfig()
    validate_inputs(snapshot, cfg)
    # Use installed code and converter; historical tool digests do not gate execution.
    values = {key: snapshot["grid"][key] for key in GRID_PARAMETERS if key in snapshot["grid"]}
    cfg = replace(cfg, **values, data_version=snapshot["version_code"])
    folder = run_basin_clip(snapshot["basin_code"], workdir / "outputs", config=cfg)
    write_archive(snapshot, folder, workdir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot")
    args = parser.parse_args()
    path = Path(args.snapshot).resolve()
    build(json.loads(path.read_text(encoding="utf-8")), path.parent)
