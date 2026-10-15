import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
export function configPath(file) {
    return file || process.env.SKILL_ROUTER_CONFIG || path.join(process.env.HOME || ".", ".config", "skill-router", "config.json");
}
export async function loadConfig(file) {
    try {
        const value = JSON.parse(await readFile(configPath(file), "utf8"));
        return { mode: value.mode || "auto", allow_external_search: !!value.allow_external_search, max_skills: Math.max(1, Number(value.max_skills || 3)), registry_urls: Array.isArray(value.registry_urls) ? value.registry_urls.map(String) : [], semantic_command: value.semantic_command ? String(value.semantic_command) : undefined };
    }
    catch {
        return { mode: "auto", allow_external_search: false, max_skills: 3, registry_urls: [] };
    }
}
export async function saveConfig(config, file) {
    const target = configPath(file);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, JSON.stringify(config, null, 2) + "\n", "utf8");
    return target;
}
