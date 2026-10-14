from __future__ import annotations

import re
from collections import defaultdict

from .models import RouteMode, RouteRequest, RouteResult, SkillMetadata, SkillSelection
from .registry import Registry


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w.-]+", text.lower()))


class SkillRouter:
    def __init__(self, registry: Registry):
        self.registry = registry

    def route(self, request: RouteRequest) -> RouteResult:
        if request.mode is RouteMode.OFF:
            return RouteResult(request.mode, "skip", reason="自动路由已关闭")
        if request.mode is RouteMode.MANUAL:
            return self._manual(request)

        skills = self.registry.list()
        selections = self._rank(request.text, skills)
        selections = self._with_dependencies(selections, skills, request.max_skills)
        if not selections:
            return RouteResult(
                request.mode,
                "external_search" if request.allow_external_search else "fallback",
                reason="本地没有达到置信度阈值的 Skill",
                external_search=request.allow_external_search,
            )

        confidence = min(1.0, selections[0].score)
        return RouteResult(
            request.mode,
            "load",
            selections,
            confidence,
            reason=self._reason(request.text, selections),
            plan=self._plan(selections, skills),
        )

    def _manual(self, request: RouteRequest) -> RouteResult:
        known = {skill.name: skill for skill in self.registry.list()}
        selected = [
            SkillSelection(name, 1.0, "用户显式指定")
            for name in request.explicit_skills
            if name in known
        ]
        unknown = [name for name in request.explicit_skills if name not in known]
        reason = "仅使用用户显式指定的 Skill"
        if unknown:
            reason += f"；未找到：{', '.join(unknown)}"
        return RouteResult(
            request.mode,
            "load" if selected else "fallback",
            selected=selected,
            confidence=1.0 if selected else 0.0,
            reason=reason,
            plan=self._plan(selected, known.values()),
        )

    def _rank(self, text: str, skills: list[SkillMetadata]) -> list[SkillSelection]:
        query = text.lower()
        words = _tokens(query)
        scored: list[SkillSelection] = []
        for skill in skills:
            metadata = set(_tokens(" ".join([
                skill.name, skill.description, *skill.domains,
                *skill.resource_types, *skill.operations, *skill.triggers,
            ])))
            overlap = len(words & metadata)
            exact_triggers = sum(1 for trigger in skill.triggers if trigger.lower() in query)
            url_bonus = 0.25 if any(marker in query for marker in ("doubao.com/docx", "/docx/", ".xlsx", ".pptx")) and (
                skill.resource_types or skill.domains
            ) else 0
            penalty = sum(0.2 for item in skill.not_for if item.lower() in query)
            score = min(1.0, overlap / max(4, min(12, len(words))) + exact_triggers * 0.2 + url_bonus - penalty)
            if score >= 0.28:
                reason = f"匹配 {overlap} 个任务词"
                if exact_triggers:
                    reason += f"，命中 {exact_triggers} 个触发词"
                scored.append(SkillSelection(skill.name, max(0.0, score), reason))
        return sorted(scored, key=lambda item: (-item.score, item.name))

    def _with_dependencies(
        self, selections: list[SkillSelection], skills: list[SkillMetadata], max_skills: int
    ) -> list[SkillSelection]:
        by_name = {skill.name: skill for skill in skills}
        result: dict[str, SkillSelection] = {item.name: item for item in selections[:max_skills]}
        for item in list(result.values()):
            for dependency in by_name.get(item.name, SkillMetadata("", "")).dependencies:
                if dependency in by_name and len(result) < max_skills:
                    result.setdefault(dependency, SkillSelection(dependency, item.score * 0.9, f"被 {item.name} 依赖"))
        return sorted(result.values(), key=lambda item: (-item.score, item.name))

    @staticmethod
    def _reason(text: str, selections: list[SkillSelection]) -> str:
        labels = ", ".join(item.name for item in selections)
        return f"根据任务内容选择 {labels}"

    @staticmethod
    def _plan(selections: list[SkillSelection], skills) -> list[dict[str, object]]:
        by_name = {skill.name: skill for skill in skills}
        return [
            {
                "skill": item.name,
                "depends_on": list(by_name[item.name].dependencies) if item.name in by_name else [],
                "reason": item.reason,
            }
            for item in selections
        ]

