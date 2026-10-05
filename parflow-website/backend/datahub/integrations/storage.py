"""Resolve task files only inside the configured job directory."""

import os
from pathlib import Path
from ..config import BACKEND
from ..common import ApiError


def job_root():
    path = Path(os.getenv("CONCN_JOB_ROOT", str(BACKEND / "jobs")))
    return (path if path.is_absolute() else BACKEND / path).resolve()


def scoped_file(key):
    root = job_root()
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise ApiError("FILE_UNAVAILABLE", 410)
    return path
