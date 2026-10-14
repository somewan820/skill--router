from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .verify import verify


EXCLUDED_NAMES = {".git", "__pycache__", ".DS_Store"}
INSTALL_RECORD = ".skill-router-install.json"


def _manifest(root: Path) -> dict:
    return json.loads((root / "skill.json").read_text(encoding="utf-8"))


def _copy_package(source: Path, destination: Path) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for item in source.iterdir():
        if item.name in EXCLUDED_NAMES or item.name == "tests":
            continue
        if item.name == INSTALL_RECORD:
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
        copied.append(str(target.relative_to(destination)))
    return sorted(copied)


def _write_record(destination: Path, manifest: dict, files: list[str]) -> None:
    (destination / INSTALL_RECORD).write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "package_id": manifest["id"],
                "version": manifest["version"],
                "files": files,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


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
    _write_record(destination_path, manifest, files)
    return {
        "installed": True,
        "source": str(source_path),
        "destination": str(destination_path),
        "package": {"id": manifest["id"], "version": manifest["version"]},
        "files": files,
    }


def uninstall(destination: str | Path, *, approve: bool = False) -> dict:
    destination_path = Path(destination).expanduser().resolve()
    record_path = destination_path / INSTALL_RECORD
    if not record_path.is_file():
        raise ValueError("installation record not found; refusing to remove an unmanaged directory")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        files = [str(item) for item in record["files"]]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid installation record: {exc}") from exc
    if not approve:
        return {
            "uninstalled": False,
            "requires_confirmation": True,
            "destination": str(destination_path),
            "package": {
                "id": record.get("package_id"),
                "version": record.get("version"),
            },
            "files": files,
        }
    removed: list[str] = []
    for relative in files:
        target = destination_path / relative
        if target.is_file() or target.is_symlink():
            target.unlink()
            removed.append(relative)
    record_path.unlink()
    try:
        for directory in sorted(
            (path for path in destination_path.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            directory.rmdir()
        destination_path.rmdir()
    except OSError:
        # Keep the directory if it contains user-managed files.
        pass
    return {
        "uninstalled": True,
        "destination": str(destination_path),
        "package": {
            "id": record.get("package_id"),
            "version": record.get("version"),
        },
        "files": removed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="skill-router-install")
    parser.add_argument("command", choices=("install", "uninstall"), nargs="?", default="install")
    parser.add_argument("--source", default=".")
    parser.add_argument("--destination", required=True)
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()
    try:
        result = (
            install(args.source, args.destination, approve=args.approve)
            if args.command == "install"
            else uninstall(args.destination, approve=args.approve)
        )
    except (OSError, ValueError, PermissionError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

