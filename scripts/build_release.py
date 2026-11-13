"""Explicit allowlist packaging; never recursively archive the workspace."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "ninebot_connect"
VERSION = json.loads((COMPONENT / "manifest.json").read_text())["version"]
OUTPUT = ROOT / "outputs"


def build() -> Path:
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / f"ninebot_connect-{VERSION}.zip"
    source = sorted(p for p in COMPONENT.rglob("*") if p.is_file() and (
        p.suffix in {".py", ".json", ".md"} or p.name in {"LICENSE", "LICENSE.kxn"}
    ) and "__pycache__" not in p.parts)
    source += [ROOT / name for name in ("README.md", "LICENSE", "docs/VERIFICATION.md")]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in source:
            archive.write(item, item.relative_to(ROOT))
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".zip.sha256").write_text(f"{checksum}  {path.name}\n")
    return path


if __name__ == "__main__":
    print(build())
