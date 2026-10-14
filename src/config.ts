import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import type { RouteMode } from "./models.js";

export interface RouterConfig { mode: RouteMode; allow_external_search: boolean; max_skills: number; registry_urls: string[]; }
export function configPath(file?: string): string {
  return file || process.env.SKILL_ROUTER_CONFIG || path.join(process.env.HOME || ".", ".config", "skill-router", "config.json");
}
export async function loadConfig(file?: string): Promise<RouterConfig> {
  try {
    const value = JSON.parse(await readFile(configPath(file), "utf8"));
    return { mode: value.mode || "auto", allow_external_search: !!value.allow_external_search, max_skills: Math.max(1, Number(value.max_skills || 3)), registry_urls: Array.isArray(value.registry_urls) ? value.registry_urls.map(String) : [] };
  } catch { return { mode: "auto", allow_external_search: false, max_skills: 3, registry_urls: [] }; }
}
export async function saveConfig(config: RouterConfig, file?: string): Promise<string> {
  const target = configPath(file);
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, JSON.stringify(config, null, 2) + "\n", "utf8");
  return target;
}
