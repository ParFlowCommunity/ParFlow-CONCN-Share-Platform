"""Public package text; source integrity and database versions remain internal."""
import hashlib

PUBLIC_VERSION = "concn1.1"
EXCLUDED_PACKAGE_FILES = frozenset({"readme.txt", "citation.txt", "sha256sums.txt"})


def package_revision():
    return hashlib.sha256(b"public-package-v3-no-text:" + PUBLIC_VERSION.encode()).hexdigest()


def public_metadata(metadata):
    result = dict(metadata)
    result["pfbas_level"] = int(result["pfbas_level"]) // 2
    result["concn_data_version"] = PUBLIC_VERSION
    for key in ("boundary_version", "clip_version", "source_manifest_sha256", "package_mode"):
        result.pop(key, None)
    return result
