import { cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { verify } from "./verify.js";

const record = ".skill-router-install.json";
const excluded = new Set([".git", "node_modules", "__pycache__", ".DS_Store", ".maka-workspace.json", "tests"]);
async function files(root: string): Promise<string[]> {
  const result: string[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (excluded.has(entry.name) || entry.name === record) continue;
    result.push(entry.name);
  }
  return result;
}
export async function install(source: string, destination: string, approve = false): Promise<Record<string, unknown>> {
  const errors = await verify(source);
  if (errors.length) throw new Error(errors.join("; "));
  const manifest = JSON.parse(await readFile(path.join(source, "skill.json"), "utf8"));
  const managed = await files(source);
  if (!approve) return { installed: false, requires_confirmation: true, source, destination, package: { id: manifest.id, version: manifest.version }, files: managed };
  await mkdir(destination, { recursive: true });
  for (const item of managed) await cp(path.join(source, item), path.join(destination, item), { recursive: true, force: true });
  await writeFile(path.join(destination, record), JSON.stringify({ package_id: manifest.id, version: manifest.version, files: managed }, null, 2) + "\n");
  return { installed: true, source, destination, package: { id: manifest.id, version: manifest.version }, files: managed };
}
export async function uninstall(destination: string, approve = false): Promise<Record<string, unknown>> {
  const marker = path.join(destination, record);
  const data = JSON.parse(await readFile(marker, "utf8"));
  if (!approve) return { uninstalled: false, requires_confirmation: true, destination, package: { id: data.package_id, version: data.version }, files: data.files };
  for (const item of data.files) await rm(path.join(destination, item), { recursive: true, force: true });
  await rm(marker, { force: true });
  return { uninstalled: true, destination, package: { id: data.package_id, version: data.version }, files: data.files };
}
