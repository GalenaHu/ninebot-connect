"""Explicit allowlist packaging; never recursively archive the workspace."""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "ninebot_connect"
VERSION = json.loads((COMPONENT / "manifest.json").read_text())["version"]
OUTPUT = ROOT / "outputs"


def build() -> Path:
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / f"ninebot_connect-{VERSION}.zip"
    source = sorted(
        p
        for p in COMPONENT.rglob("*")
        if p.is_file()
        and (p.suffix in {".py", ".json", ".md", ".png"} or p.name in {"LICENSE", "LICENSE.kxn"})
        and "__pycache__" not in p.parts
    )
    source += [
        ROOT / name for name in ("hacs.json", "README.md", "LICENSE", "docs/VERIFICATION.md")
    ]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in source:
            archive.write(item, item.relative_to(ROOT))
    source_path = OUTPUT / f"ninebot_connect-{VERSION}-source.zip"
    development = [
        ROOT / name
        for name in (
            "pyproject.toml",
            "requirements-dev.txt",
            "docs/SPEC.md",
            "docs/EXPANSION.md",
            "docs/REVIEW.md",
            "scripts/build_release.py",
            "scripts/build_brand.py",
        )
    ] + sorted((ROOT / "tests").glob("*.py"))
    with zipfile.ZipFile(source_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in source + development:
            archive.write(item, item.relative_to(ROOT))
    for release in (path, source_path):
        checksum = hashlib.sha256(release.read_bytes()).hexdigest()
        release.with_suffix(".zip.sha256").write_text(f"{checksum}  {release.name}\n")
    return path


if __name__ == "__main__":
    print(build())
