from __future__ import annotations

import re
from collections import defaultdict

from .models import RouteMode, RouteRequest, RouteResult, SkillMetadata, SkillSelection
from .registry import Registry


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w.-]+", text.lower()))


INTENT_ALIASES = {
    "审查": ("review", "code"),
    "评审": ("review", "code"),
    "代码审查": ("code", "review"),
    "代码评审": ("code", "review"),
    "代码变更": ("code", "diff", "change"),
    "当前分支": ("branch", "diff"),
    "安全性": ("security",),
    "回归风险": ("regression",),
    "兼容性": ("compatibility",),
    "创建": ("create",),
    "工单": ("ticket", "issue"),
    "问题": ("finding", "issue"),
    "项目": ("project",),
    "关联": ("link", "associate"),
}


def _expanded_tokens(text: str) -> set[str]:
    tokens = _tokens(text)
    for phrase, aliases in INTENT_ALIASES.items():
        if phrase in text:
            tokens.update(aliases)
    return tokens


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


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
        words = _expanded_tokens(query)
        scored: list[SkillSelection] = []
        for skill in skills:
            metadata = set(_tokens(" ".join([
                skill.name, skill.description, *skill.domains,
                *skill.resource_types, *skill.operations, *skill.triggers,
            ])))
            overlap = len(words & metadata)
            exact_triggers = sum(1 for trigger in skill.triggers if trigger.lower() in query)
            exact_name = 0.35 if skill.name.lower() in query else 0
            url_bonus = 0.25 if any(marker in query for marker in ("doubao.com/docx", "/docx/", ".xlsx", ".pptx")) and (
                skill.resource_types or skill.domains
            ) else 0
            penalty = sum(0.2 for item in skill.not_for if item.lower() in query)
            score = min(
                1.0,
                overlap / max(4, min(10, len(words)))
                + exact_triggers * 0.2
                + exact_name
                + url_bonus
                - penalty,
            )
            # A general code-change request should not activate a simplification
            # audit unless simplification is actually part of the task.
            if "simplif" in " ".join(metadata) and not _has_any(
                query, ("简化", "simplify", "simplification", "熵回收", "dead code")
            ):
                score -= 0.25
            if score >= 0.28:
                reason = f"匹配 {overlap} 个任务词"
                if exact_triggers:
                    reason += f"，命中 {exact_triggers} 个触发词"
                if exact_name:
                    reason += "，命中 Skill 名称"
                scored.append(SkillSelection(skill.name, max(0.0, score), reason))

        ranked = sorted(scored, key=lambda item: (-item.score, item.name))
        names = {item.name for item in ranked}
        # code-review and review-agent overlap substantially. Prefer the
        # user-facing code review Skill for ordinary branch/PR review tasks.
        if {"code-review", "review-agent"} <= names and _has_any(
            query, ("代码", "分支", "pr", "pull request", "diff", "变更")
        ):
            ranked = [item for item in ranked if item.name != "review-agent"]
        return ranked

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

