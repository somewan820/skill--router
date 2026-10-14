import { readFile } from "node:fs/promises";
import path from "node:path";
import { request } from "node:https";
import { request as httpRequest } from "node:http";
import type { SkillMetadata } from "./models.js";
import { parseSkill } from "./metadata.js";

export interface Registry {
  list(): Promise<SkillMetadata[]>;
  search(query: string): Promise<SkillMetadata[]>;
}

async function walk(root: string): Promise<string[]> {
  const { readdir } = await import("node:fs/promises");
  const entries = await readdir(root, { withFileTypes: true }).catch(() => []);
  const files: string[] = [];
  for (const entry of entries) {
    if (entry.name === "node_modules" || entry.name === "__pycache__" || entry.name === ".git") continue;
    const full = path.join(root, entry.name);
    if (entry.isDirectory()) files.push(...await walk(full));
    else if (entry.name === "SKILL.md") files.push(full);
  }
  return files;
}

export class LocalRegistry implements Registry {
  constructor(private readonly roots: string[]) {}

  async list(): Promise<SkillMetadata[]> {
    const found = new Map<string, SkillMetadata>();
    for (const root of this.roots.map((item) => item.replace(/^~/, process.env.HOME || ""))) {
      const files = await walk(root);
      for (const file of files) {
        const skill = await parseSkill(file);
        if (skill && !found.has(skill.name)) found.set(skill.name, skill);
      }
    }
    return [...found.values()].sort((a, b) => a.name.localeCompare(b.name));
  }

  async search(query: string): Promise<SkillMetadata[]> {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    return (await this.list()).map((skill) => {
      const haystack = [skill.name, skill.description, ...(skill.domains || []), ...(skill.operations || []), ...(skill.triggers || [])].join(" ").toLowerCase();
      return { skill, score: words.filter((word) => haystack.includes(word)).length };
    }).filter((item) => item.score > 0).sort((a, b) => b.score - a.score || a.skill.name.localeCompare(b.skill.name)).map((item) => item.skill);
  }
}

function remoteJson(url: string): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const client = parsed.protocol === "https:" ? request : httpRequest;
    const req = client(parsed, { headers: { accept: "application/json", "user-agent": "skill-router/0.2" } }, (res: import("node:http").IncomingMessage) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk: string) => body += chunk);
      res.on("end", () => res.statusCode && res.statusCode >= 200 && res.statusCode < 300 ? resolve(JSON.parse(body)) : reject(new Error(`Registry HTTP ${res.statusCode}`)));
    });
    req.on("error", reject);
    req.end();
  });
}

export class HttpRegistry {
  readonly name: string;
  constructor(private readonly endpoint: string) {
    this.name = new URL(endpoint).host;
  }
  async search(query: string): Promise<SkillMetadata[]> {
    const url = new URL(this.endpoint);
    url.searchParams.set("q", query);
    const payload = await remoteJson(url.toString());
    const items = Array.isArray(payload) ? payload : (payload as { skills?: unknown[] })?.skills || [];
    return items.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null).map((item) => ({
      name: String(item.name || item.id || ""),
      description: String(item.description || ""),
      source: this.name,
      version: item.version ? String(item.version) : undefined,
      domains: Array.isArray(item.domains) ? item.domains.map(String) : [],
      resource_types: Array.isArray(item.resource_types) ? item.resource_types.map(String) : [],
      operations: Array.isArray(item.operations) ? item.operations.map(String) : [],
      triggers: Array.isArray(item.triggers) ? item.triggers.map(String) : [],
      dependencies: Array.isArray(item.dependencies) ? item.dependencies.map(String) : [],
      exclusive_group: item.exclusive_group ? String(item.exclusive_group) : undefined,
      priority: Number(item.priority || 0),
    })).filter((item) => item.name && item.description);
  }
}
