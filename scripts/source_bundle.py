"""Create a credentials-free, explicitly scoped Docker build bundle for Lima."""
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / ".tools" / "docker-source.tar.gz"
output.parent.mkdir(exist_ok=True)
allowed = ["Dockerfile", ".dockerignore", "compose.yaml", "requirements-web.txt", "requirements-dev.txt",
           "src", "investigator_runtime", "tests", "data", "scripts"]
with tarfile.open(output, "w:gz") as bundle:
    for name in allowed:
        path = root / name
        paths = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file in paths:
            if file.is_file() and not file.is_symlink() and not any(part == "__pycache__" for part in file.parts):
                bundle.add(file, arcname=str(file.relative_to(root)), recursive=False)
print(output)
