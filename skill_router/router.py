from __future__ import annotations

import re

from .models import RouteMode, RouteRequest, RouteResult, SkillMetadata, SkillSelection
from .registry import Registry


def _tokens(text: str) -> set[str]:
    """Tokenize Latin words and CJK n-grams without domain-specific synonyms."""
    lower = text.lower()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9_.-]*", lower))
    for run in re.findall(r"[\u3400-\u9fff]+", lower):
        tokens.update(run)
        tokens.update(run[index:index + 2] for index in range(len(run) - 1))
    return tokens


def _contains(text: str, values: tuple[str, ...]) -> int:
    return sum(1 for value in values if value.lower() in text)


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

        return RouteResult(
            request.mode,
            "load",
            selections,
            min(1.0, selections[0].score),
            reason=self._reason(selections),
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
        query_tokens = _tokens(query)
        scored: list[tuple[SkillSelection, SkillMetadata]] = []
        for skill in skills:
            name_tokens = _tokens(skill.name)
            metadata_tokens = _tokens(" ".join([
                skill.name,
                skill.description,
                *skill.domains,
                *skill.resource_types,
                *skill.operations,
                *skill.triggers,
            ]))
            token_overlap = len(query_tokens & metadata_tokens)
            name_overlap = len(query_tokens & name_tokens)
            trigger_hits = _contains(query, skill.triggers)
            excluded_hits = _contains(query, skill.not_for)
            # Structured triggers and exact Skill names are intentionally
            # stronger than incidental description-word overlap.
            score = (
                min(0.35, token_overlap / max(8, len(query_tokens)))
                + min(0.5, trigger_hits * 0.25)
                + min(0.35, name_overlap * 0.2)
                + skill.priority * 0.01
                - min(0.5, excluded_hits * 0.2)
            )
            if score < 0.28:
                continue
            reasons = [f"匹配 {token_overlap} 个元数据词"]
            if trigger_hits:
                reasons.append(f"命中 {trigger_hits} 个触发词")
            if name_overlap:
                reasons.append("命中 Skill 名称")
            scored.append((SkillSelection(skill.name, min(1.0, max(0.0, score)), "，".join(reasons)), skill))

        ranked: list[tuple[SkillSelection, SkillMetadata]] = []
        groups: dict[str, tuple[SkillSelection, SkillMetadata]] = {}
        for selection, skill in sorted(scored, key=lambda item: (-item[0].score, -item[1].priority, item[0].name)):
            if skill.exclusive_group:
                current = groups.get(skill.exclusive_group)
                if current:
                    continue
                groups[skill.exclusive_group] = (selection, skill)
            ranked.append((selection, skill))
        return [selection for selection, _ in ranked]

    def _with_dependencies(
        self, selections: list[SkillSelection], skills: list[SkillMetadata], max_skills: int
    ) -> list[SkillSelection]:
        by_name = {skill.name: skill for skill in skills}
        result: dict[str, SkillSelection] = {item.name: item for item in selections[:max_skills]}
        for item in list(result.values()):
            for dependency in by_name.get(item.name, SkillMetadata("", "")).dependencies:
                if dependency in by_name and len(result) < max_skills:
                    result.setdefault(
                        dependency,
                        SkillSelection(dependency, item.score * 0.9, f"被 {item.name} 依赖"),
                    )
        return sorted(result.values(), key=lambda item: (-item.score, item.name))

    @staticmethod
    def _reason(selections: list[SkillSelection]) -> str:
        return f"根据任务内容选择 {', '.join(item.name for item in selections)}"

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
