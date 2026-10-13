"""Vercel entrypoint for the public, read-only VerifyOps engineering showcase."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

os.environ["VDIR_LOAD_DOTENV"] = "0"
os.environ["VDIR_PUBLIC_SHOWCASE"] = "1"

from vdir.api import create_app  # noqa: E402

app = create_app(state_dir="/tmp/verifyops-public-showcase", token="", public_origin="", operator="public-showcase")
