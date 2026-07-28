"""Load the same telemetry implementation used by exported investigator workers."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / "agents/investigator" / "telemetry.py"
_spec = importlib.util.spec_from_file_location("vdir_runtime_telemetry", _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
Telemetry = _module.Telemetry
