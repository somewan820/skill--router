from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

from .models import SkillMetadata


class Registry(Protocol):
    def list(self) -> list[SkillMetadata]: ...

    def search(self, query: str) -> list[SkillMetadata]: ...


def _parse_frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    values: dict[str, object] = {}
    for line in parts[1].splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        raw = raw.strip()
        if raw.startswith("[") and raw.endswith("]"):
            try:
                value = json.loads(raw.replace("'", '"'))
            except json.JSONDecodeError:
                value = [item.strip().strip("'\"") for item in raw[1:-1].split(",") if item.strip()]
        else:
            value = raw.strip("'\"")
        values[key.strip()] = value
    return values


def _tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def parse_skill(path: Path) -> SkillMetadata | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    data = _parse_frontmatter(text)
    name = str(data.get("name") or path.parent.name)
    description = str(data.get("description") or "").strip()
    if not name or not description:
        return None
    return SkillMetadata(
        name=name,
        description=description,
        location=str(path.parent),
        domains=_tuple(data.get("domains")),
        resource_types=_tuple(data.get("resource_types")),
        operations=_tuple(data.get("operations")),
        triggers=_tuple(data.get("triggers")),
        not_for=_tuple(data.get("not_for")),
        related_skills=_tuple(data.get("related_skills")),
        dependencies=_tuple(data.get("dependencies")),
        version=str(data["version"]) if data.get("version") else None,
    )


class LocalRegistry:
    def __init__(self, roots: list[str | Path]):
        self.roots = [Path(root).expanduser() for root in roots]

    def list(self) -> list[SkillMetadata]:
        found: dict[str, SkillMetadata] = {}
        for root in self.roots:
            if not root.exists():
                continue
            paths = [root / "SKILL.md"] if (root / "SKILL.md").is_file() else root.glob("**/SKILL.md")
            for path in paths:
                skill = parse_skill(path)
                if skill and skill.name not in found:
                    found[skill.name] = skill
        return sorted(found.values(), key=lambda skill: skill.name)

    def search(self, query: str) -> list[SkillMetadata]:
        words = set(re.findall(r"[\w.-]+", query.lower()))
        scored: list[tuple[int, SkillMetadata]] = []
        for skill in self.list():
            haystack = " ".join(
                [skill.name, skill.description, *skill.domains, *skill.resource_types, *skill.operations, *skill.triggers]
            ).lower()
            score = sum(1 for word in words if word in haystack)
            if score:
                scored.append((score, skill))
        return [skill for _, skill in sorted(scored, key=lambda item: (-item[0], item[1].name))]


class ExternalRegistry(Protocol):
    """Adapter boundary for skills.sh, SkillsMP, or a private registry."""

    name: str

    def search(self, query: str) -> list[SkillMetadata]: ...

    def get_metadata(self, skill_id: str) -> SkillMetadata | None: ...

    def install(self, skill_id: str, destination: Path, *, approved: bool = False) -> Path:
        """Install only after explicit approval; implementations must not auto-install."""
        ...

