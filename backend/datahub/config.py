"""Stable repository paths and local environment loading."""

from pathlib import Path
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"
load_dotenv(BACKEND / ".env")
