"""Public package text; source integrity and database versions remain internal."""
import hashlib
from datetime import datetime, timezone

PUBLIC_VERSION = "concn1.1"
# README/SHA256SUMS 仍不进入下载包。
EXCLUDED_PACKAGE_FILES = frozenset({"readme.txt", "sha256sums.txt"})
# CITATION.txt 随包发布（条款与许可文字都指向它）。内容由平台按数据版本生成，
# 因此流水线若自带同名文件一律丢弃，改用平台版本，避免发出过期引用文字。
CITATION_NAME = "CITATION.txt"
REPLACED_PACKAGE_FILES = frozenset({CITATION_NAME.lower()})


def package_revision():
    return hashlib.sha256(b"public-package-v4-citation:" + PUBLIC_VERSION.encode()).hexdigest()


def citation_text(snapshot):
    """下载包内的 CITATION.txt 正文；引用条目取自数据版本，不在此处硬编码。"""
    citation = (snapshot.get("citation") or "").strip()
    return (
        "ParFlow CONCN 数据引用要求 / Citation requirements\n"
        "==================================================\n\n"
        "使用本数据包开展的成果，请在论文、报告或数据说明中引用以下文献：\n"
        "If you use this package in a publication or report, please cite:\n\n"
        f"{citation}\n\n"
        f"数据版本 / Data version: {snapshot.get('version_code', '')}\n"
        f"流域编号 / Basin code: {snapshot.get('basin_code', '')}\n\n"
        "本文件由平台在生成裁切包时写入。\n"
        "This file is written by the platform when the clipping package is produced.\n"
        f"生成时间 / Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
    )


def public_metadata(metadata):
    result = dict(metadata)
    result["pfbas_level"] = int(result["pfbas_level"]) // 2
    result["concn_data_version"] = PUBLIC_VERSION
    for key in ("boundary_version", "clip_version", "source_manifest_sha256", "package_mode"):
        result.pop(key, None)
    return result
