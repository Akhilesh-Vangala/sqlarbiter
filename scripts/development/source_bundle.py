"""Create a credentials-free, explicitly scoped Docker build bundle for Lima."""
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
output = root / ".tools" / "docker-source.tar.gz"
output.parent.mkdir(exist_ok=True)
allowed = [".dockerignore", "infrastructure/containers/compose.yaml", "pyproject.toml", "backend/docker/Dockerfile", "backend/src", "backend/tests", "backend/agents/investigator", "backend/requirements/runtime.txt", "backend/requirements/development.txt", "backend/requirements/dbt.txt", "frontend", "backend/data", "backend/dbt", "scripts"]
with tarfile.open(output, "w:gz") as bundle:
    for name in allowed:
        path = root / name
        paths = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file in paths:
            if file.is_file() and not file.is_symlink() and not any(part in ("__pycache__", "node_modules", ".tools", ".terraform") or part.startswith((".env", ".venv")) for part in file.relative_to(root).parts):
                bundle.add(file, arcname=str(file.relative_to(root)), recursive=False)
print(output)
