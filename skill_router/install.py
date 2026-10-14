from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .verify import verify


EXCLUDED_NAMES = {".git", "__pycache__", ".DS_Store"}


def _manifest(root: Path) -> dict:
    return json.loads((root / "skill.json").read_text(encoding="utf-8"))


def _copy_package(source: Path, destination: Path) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for item in source.iterdir():
        if item.name in EXCLUDED_NAMES or item.name == "tests":
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
        copied.append(str(target.relative_to(destination)))
    return sorted(copied)


def install(source: str | Path, destination: str | Path, *, approve: bool = False) -> dict:
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    errors = verify(source_path)
    if errors:
        raise ValueError("invalid Skill package: " + "; ".join(errors))
    manifest = _manifest(source_path)
    if destination_path.exists() and any(destination_path.iterdir()) and not approve:
        raise PermissionError("destination is not empty; pass --approve to replace package files")
    if not approve:
        return {
            "installed": False,
            "requires_confirmation": True,
            "source": str(source_path),
            "destination": str(destination_path),
            "package": {"id": manifest["id"], "version": manifest["version"]},
            "files": sorted(
                str(item.relative_to(source_path))
                for item in source_path.rglob("*")
                if item.is_file() and not any(part in EXCLUDED_NAMES or part == "tests" for part in item.parts)
            ),
        }
    files = _copy_package(source_path, destination_path)
    return {
        "installed": True,
        "source": str(source_path),
        "destination": str(destination_path),
        "package": {"id": manifest["id"], "version": manifest["version"]},
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="skill-router-install")
    parser.add_argument("--source", default=".")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()
    try:
        result = install(args.source, args.destination, approve=args.approve)
    except (OSError, ValueError, PermissionError) as exc:
        print(json.dumps({"installed": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

