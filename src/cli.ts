#!/usr/bin/env node
import process from "node:process";
import { configPath, loadConfig, saveConfig, type RouterConfig } from "./config.js";
import { install, uninstall } from "./install.js";
import { LocalRegistry, HttpRegistry } from "./registry.js";
import { SkillRouter } from "./router.js";
import { verify } from "./verify.js";
import type { RouteMode } from "./models.js";

const args = process.argv.slice(2);
const value = (name: string): string | undefined => { const index = args.indexOf(name); return index >= 0 ? args[index + 1] : undefined; };
const many = (name: string): string[] => args.flatMap((item: string, index: number) => item === name && args[index + 1] ? [args[index + 1]] : []);
const has = (name: string) => args.includes(name);
const json = (value: unknown) => console.log(JSON.stringify(value, null, 2));
const commandNames = new Set(["route", "search", "config", "status", "install", "uninstall", "verify"]);
const command = args.find((item) => commandNames.has(item));
const configFile = value("--config-file");
const optionValues = new Set(["--config-file", "--skills-dir", "--registry-url", "--mode", "--max-skills", "--use", "--source", "--destination", "--path"]);
function positional(): string[] {
  const commandIndex = command ? args.indexOf(command) : 0;
  const rest = args.slice(commandIndex + 1);
  const result: string[] = [];
  for (let index = 0; index < rest.length; index++) {
    const item = rest[index];
    if (item.startsWith("--")) {
      if (optionValues.has(item)) index++;
      continue;
    }
    result.push(item);
  }
  return result;
}

async function main(): Promise<void> {
  const config = await loadConfig(configFile);
  if (command === "config") {
    const updated: RouterConfig = { mode: (value("--mode") as RouteMode) || config.mode, allow_external_search: value("--allow-external-search") === "true" || (has("--allow-external-search") ? true : config.allow_external_search), max_skills: Number(value("--max-skills") || config.max_skills), registry_urls: many("--registry-url").length ? many("--registry-url") : config.registry_urls };
    json({ saved: await saveConfig(updated, configFile), ...updated }); return;
  }
  if (command === "status") { json({ config_file: configPath(configFile), ...config }); return; }
  if (command === "verify") { const errors = await verify(value("--path") || "."); json({ valid: !errors.length, errors }); process.exitCode = errors.length ? 1 : 0; return; }
  if (command === "install" || command === "uninstall") {
    const destination = value("--destination"); if (!destination) throw new Error("--destination is required");
    json(command === "install" ? await install(value("--source") || ".", destination, has("--approve")) : await uninstall(destination, has("--approve"))); return;
  }
  const roots = many("--skills-dir").length ? many("--skills-dir") : (process.env.SKILL_ROUTER_SKILLS_DIR || `${process.env.HOME}/.codex/skills:${process.env.HOME}/.cursor/skills`).split(":");
  const local = new LocalRegistry(roots);
  const external = (many("--registry-url").length ? many("--registry-url") : config.registry_urls).map((url) => new HttpRegistry(url));
  const query = positional().join(" ");
  if (command === "search") { json({ query, results: await local.search(query), external: has("--external") ? (await Promise.all(external.map((item) => item.search(query).catch(() => [])))).flat() : [] }); return; }
  if (command === "route") { json(await new SkillRouter(local, external).route({ text: query, mode: (value("--mode") as RouteMode) || config.mode, explicit_skills: many("--use"), allow_external_search: has("--allow-external-search") || config.allow_external_search, max_skills: Number(value("--max-skills") || config.max_skills) })); return; }
  throw new Error("commands: route, search, config, status, install, uninstall, verify");
}
main().catch((error) => { console.error(JSON.stringify({ error: String(error.message || error) })); process.exitCode = 1; });
