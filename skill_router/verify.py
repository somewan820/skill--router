from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_MANIFEST_FIELDS = ("schema_version", "id", "name", "version", "description")


def verify(path: str | Path = ".") -> list[str]:
    root = Path(path).expanduser().resolve()
    errors: list[str] = []
    manifest_path = root / "skill.json"
    skill_path = root / "SKILL.md"
    if not manifest_path.is_file():
        errors.append("missing skill.json")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"invalid skill.json: {exc}")
        else:
            for field in REQUIRED_MANIFEST_FIELDS:
                if not manifest.get(field):
                    errors.append(f"skill.json missing {field}")
            if manifest.get("id") and not skill_path.is_file():
                errors.append("manifest declares a Skill but SKILL.md is missing")
    if not skill_path.is_file():
        errors.append("missing SKILL.md")
    elif not skill_path.read_text(encoding="utf-8").startswith("---"):
        errors.append("SKILL.md is missing YAML frontmatter")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(prog="skill-router-verify")
    parser.add_argument("--path", default=".")
    args = parser.parse_args()
    errors = verify(args.path)
    if errors:
        print(json.dumps({"valid": False, "path": str(Path(args.path).resolve()), "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"valid": True, "path": str(Path(args.path).resolve())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

