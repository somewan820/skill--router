from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RouteMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    OFF = "off"


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str
    source: str = "local"
    location: str | None = None
    domains: tuple[str, ...] = ()
    resource_types: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    triggers: tuple[str, ...] = ()
    not_for: tuple[str, ...] = ()
    related_skills: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    exclusive_group: str | None = None
    priority: int = 0
    version: str | None = None


@dataclass(frozen=True)
class RouteRequest:
    text: str
    mode: RouteMode = RouteMode.AUTO
    explicit_skills: tuple[str, ...] = ()
    allow_external_search: bool = False
    max_skills: int = 3


@dataclass(frozen=True)
class SkillSelection:
    name: str
    score: float
    reason: str


@dataclass
class RouteResult:
    mode: RouteMode
    action: str
    selected: list[SkillSelection] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
    external_search: bool = False
    install_required: bool = False
    warnings: list[str] = field(default_factory=list)
    external_candidates: list[dict[str, Any]] = field(default_factory=list)
    plan: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "action": self.action,
            "selected": [item.name for item in self.selected],
            "selections": [
                {"name": item.name, "score": round(item.score, 3), "reason": item.reason}
                for item in self.selected
            ],
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "external_search": self.external_search,
            "install_required": self.install_required,
            "warnings": self.warnings,
            "external_candidates": self.external_candidates,
            "plan": self.plan,
        }

