"""Load only this project's ignored local configuration, without printing values."""
import os
from pathlib import Path


def load_local_configuration():
    if os.environ.get("VDIR_LOAD_DOTENV", "1") == "0":
        return
    from dotenv import load_dotenv
    path = Path(__file__).resolve().parents[3] / ".env"
    if path.is_file():
        load_dotenv(path, override=False)
