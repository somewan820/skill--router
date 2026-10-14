from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .models import RouteMode


@dataclass(frozen=True)
class RouterConfig:
    mode: RouteMode = RouteMode.AUTO
    allow_external_search: bool = False
    max_skills: int = 3


def default_path() -> Path:
    override = os.environ.get("SKILL_ROUTER_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "skill-router" / "config.json"


def load(path: str | Path | None = None) -> RouterConfig:
    config_path = Path(path).expanduser() if path else default_path()
    if not config_path.is_file():
        return RouterConfig()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return RouterConfig()
    try:
        return RouterConfig(
            mode=RouteMode(raw.get("mode", RouteMode.AUTO.value)),
            allow_external_search=bool(raw.get("allow_external_search", False)),
            max_skills=max(1, int(raw.get("max_skills", 3))),
        )
    except (TypeError, ValueError):
        return RouterConfig()


def save(config: RouterConfig, path: str | Path | None = None) -> Path:
    config_path = Path(path).expanduser() if path else default_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "mode": config.mode.value,
                "allow_external_search": config.allow_external_search,
                "max_skills": config.max_skills,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return config_path
