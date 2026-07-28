"""Vercel entrypoint for VerifyOps samples and request-bounded visitor CSVs."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend" / "src"))

os.environ["VDIR_LOAD_DOTENV"] = "0"
os.environ["VDIR_PUBLIC_SHOWCASE"] = "1"
os.environ["VDIR_PUBLIC_DEMO"] = "1"
os.environ["VDIR_DATABASE_URL"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

from vdir.api.routes import create_app  # noqa: E402

app = create_app(state_dir="/tmp/verifyops-public-showcase", token="", public_origin="", operator="public-showcase")
