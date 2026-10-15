function tokens(text) {
    const lower = text.toLowerCase();
    const result = new Set(lower.match(/[a-z0-9][a-z0-9_.-]*/g) || []);
    for (const run of lower.match(/[\u3400-\u9fff]+/g) || []) {
        [...run].forEach((char) => result.add(char));
        for (let i = 0; i < run.length - 1; i++)
            result.add(run.slice(i, i + 2));
    }
    return result;
}
function triggerMatches(query, trigger, queryTokens) {
    if (query.includes(trigger.toLowerCase()))
        return true;
    if (/[\u3400-\u9fff]/.test(trigger)) {
        const characters = [...trigger.toLowerCase()].filter((character) => /[\u3400-\u9fff]/.test(character));
        return characters.length > 0 && characters.every((character) => query.includes(character));
    }
    const triggerTokens = new Set([...tokens(trigger)].filter((token) => !/[\u3400-\u9fff]/.test(token) || token.length <= 2));
    return triggerTokens.size > 0 && [...triggerTokens].every((token) => queryTokens.has(token));
}
export class SkillRouter {
    registry;
    external;
    semantic;
    constructor(registry, external = [], semantic) {
        this.registry = registry;
        this.external = external;
        this.semantic = semantic;
    }
    async route(request) {
        const mode = request.mode || "auto";
        if (mode === "off")
            return this.result(mode, "skip", [], "自动路由已关闭");
        const skills = await this.registry.list();
        if (mode === "manual") {
            const selected = (request.explicit_skills || []).filter((name) => skills.some((skill) => skill.name === name))
                .map((name) => ({ name, score: 1, reason: "用户显式指定" }));
            return this.result(mode, selected.length ? "load" : "fallback", selected, "仅使用用户显式指定的 Skill");
        }
        let selected = this.rank(request.text, skills);
        let semanticUsed = false;
        if (!selected.length && request.semantic && this.semantic) {
            try {
                semanticUsed = true;
                selected = (await this.semantic.rank(request.text, skills.slice(0, 20)))
                    .filter((item) => skills.some((skill) => skill.name === item.name))
                    .filter((item) => item.confidence >= 0.6)
                    .map((item) => ({ name: item.name, score: Math.min(1, Math.max(0, item.confidence)), reason: item.reason }));
            }
            catch (error) {
                return {
                    ...this.result(mode, "fallback", [], "语义 Provider 不可用"),
                    warnings: [`语义 Provider 失败：${String(error instanceof Error ? error.message : error)}`],
                };
            }
        }
        const [ordered, warnings] = this.dependencies(selected, skills, request.max_skills || 3);
        if (!ordered.length) {
            const candidates = request.allow_external_search ? await this.externalCandidates(request.text) : [];
            return {
                ...this.result(mode, candidates.length ? "external_candidates" : request.allow_external_search ? "external_search" : "fallback", [], "本地没有达到置信度阈值的 Skill"),
                external_search: Boolean(request.allow_external_search && !candidates.length),
                external_candidates: candidates,
            };
        }
        selected = ordered;
        const confidence = Math.min(...selected.map((item) => item.score));
        const action = semanticUsed
            ? confidence >= 0.85 ? "load" : confidence >= 0.6 ? "confirm" : "fallback"
            : "load";
        if (semanticUsed && action === "fallback") {
            return {
                ...this.result(mode, action, [], "语义匹配置信度过低"),
                warnings: ["语义匹配低于 0.60，未自动加载 Skill"],
            };
        }
        return {
            ...this.result(mode, action, selected, action === "confirm" ? "语义匹配需要用户确认" : `根据任务内容选择 ${selected.map((item) => item.name).join(", ")}`),
            confidence,
            warnings,
            plan: selected.map((item) => ({ skill: item.name, depends_on: skills.find((skill) => skill.name === item.name)?.dependencies || [], reason: item.reason })),
        };
    }
    result(mode, action, selections, reason) {
        return {
            mode, action, selected: selections.map((item) => item.name), selections,
            confidence: selections[0]?.score || 0, reason, external_search: false,
            install_required: false, warnings: [], external_candidates: [], plan: [],
        };
    }
    rank(text, skills) {
        const query = text.toLowerCase();
        const queryTokens = tokens(query);
        const scored = skills.map((skill) => {
            const metadata = [skill.name, skill.description, ...(skill.domains || []), ...(skill.resource_types || []), ...(skill.operations || []), ...(skill.triggers || [])];
            const metadataTokens = tokens(metadata.join(" "));
            const overlap = [...queryTokens].filter((token) => metadataTokens.has(token)).length;
            const nameOverlap = [...tokens(skill.name)].filter((token) => queryTokens.has(token)).length;
            const triggerHits = (skill.triggers || []).filter((trigger) => triggerMatches(query, trigger, queryTokens)).length;
            const excludedHits = (skill.not_for || []).filter((term) => query.includes(term.toLowerCase())).length;
            const score = Math.min(1, Math.min(.35, overlap / Math.max(8, queryTokens.size)) + Math.min(.6, triggerHits * .3) + Math.min(.35, nameOverlap * .2) + (skill.priority || 0) * .01 - Math.min(.5, excludedHits * .2));
            return { skill, selection: { name: skill.name, score: Math.max(0, score), reason: `匹配 ${overlap} 个元数据词${triggerHits ? `，命中 ${triggerHits} 个触发词` : ""}` } };
        }).filter((item) => item.selection.score >= .25).sort((a, b) => b.selection.score - a.selection.score || (b.skill.priority || 0) - (a.skill.priority || 0));
        const groups = new Set();
        return scored.filter(({ skill }) => !skill.exclusive_group || !groups.has(skill.exclusive_group) && !!groups.add(skill.exclusive_group)).slice(0, 20).map((item) => item.selection);
    }
    dependencies(selected, skills, max) {
        const byName = new Map(skills.map((skill) => [skill.name, skill]));
        const result = new Map(selected.slice(0, max).map((item) => [item.name, item]));
        const queue = [...result.values()];
        while (queue.length) {
            const current = queue.shift();
            for (const dependency of byName.get(current.name)?.dependencies || []) {
                if (byName.has(dependency) && result.size < max && !result.has(dependency)) {
                    const item = { name: dependency, score: current.score * .9, reason: `被 ${current.name} 依赖` };
                    result.set(dependency, item);
                    queue.push(item);
                }
            }
        }
        const ordered = [];
        const visited = new Set();
        const visiting = new Set();
        const warnings = [];
        const visit = (name, trail = []) => {
            if (visited.has(name))
                return;
            if (visiting.has(name)) {
                warnings.push(`检测到 Skill 依赖环：${[...trail, name].join(" -> ")}`);
                return;
            }
            visiting.add(name);
            for (const dep of byName.get(name)?.dependencies || [])
                if (result.has(dep))
                    visit(dep, [...trail, name]);
            visiting.delete(name);
            visited.add(name);
            ordered.push(result.get(name));
        };
        for (const name of result.keys())
            visit(name);
        return [ordered, [...new Set(warnings)]];
    }
    async externalCandidates(text) {
        const result = [];
        for (const registry of this.external) {
            try {
                for (const skill of await registry.search(text))
                    result.push({ name: skill.name, description: skill.description, source: skill.source, version: skill.version, operations: skill.operations || [] });
            }
            catch { /* an unavailable registry must not block local routing */ }
        }
        return result;
    }
}
