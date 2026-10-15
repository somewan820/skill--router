import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const exec = promisify(execFile);
const cli = path.resolve("dist/cli.js");

async function fixture() {
  const root = await mkdtemp(path.join(tmpdir(), "skill-router-ts-"));
  await mkdir(path.join(root, "renderer"));
  await writeFile(path.join(root, "renderer", "SKILL.md"), `---
name: renderer
description: Render a final artifact
operations: [render]
triggers: [render]
---
# renderer
`);
  return root;
}

test("route discovers a local Skill", async () => {
  const root = await fixture();
  try {
    const result = JSON.parse((await exec("node", [cli, "--skills-dir", root, "route", "render an artifact"])).stdout);
    assert.deepEqual(result.selected, ["renderer"]);
    assert.equal(result.action, "load");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("off mode skips routing", async () => {
  const result = JSON.parse((await exec("node", [cli, "--skills-dir", "/missing", "route", "--mode", "off", "render"])).stdout);
  assert.equal(result.action, "skip");
});

test("structured triggers compose a complex task", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "skill-router-complex-"));
  try {
    for (const [name, body] of [
      ["reviewer", "---\nname: reviewer\ndescription: Review changes\ntriggers: [代码审查, 回归]\n---\n"],
      ["exporter", "---\nname: exporter\ndescription: Export a report\ntriggers: [导出报告]\ndependencies: [reviewer]\n---\n"],
    ]) {
      await mkdir(path.join(root, name));
      await writeFile(path.join(root, name, "SKILL.md"), body);
    }
    const result = JSON.parse((await exec("node", [cli, "--skills-dir", root, "route", "请审查代码并导出审查报告"])).stdout);
    assert.deepEqual(result.selected, ["reviewer", "exporter"]);
    assert.deepEqual(result.plan[1].depends_on, ["reviewer"]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("semantic provider protocol can recover a natural-language match", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "skill-router-semantic-"));
  try {
    await mkdir(path.join(root, "installer"));
    await writeFile(path.join(root, "installer", "SKILL.md"), `---
name: installer
description: Install skills from a repository
---
# installer
`);
    const provider = path.join(root, "provider.mjs");
    await writeFile(provider, `
let input = "";
process.stdin.on("data", chunk => input += chunk);
process.stdin.on("end", () => {
  const payload = JSON.parse(input);
  const match = payload.candidates.find(item => item.name === "installer");
  process.stdout.write(JSON.stringify({ selections: [{ name: match.name, confidence: 0.96, reason: "semantic match" }] }));
});
`);
    const result = JSON.parse((await exec("node", [
      cli, "--skills-dir", root, "route", "--semantic", "--semantic-command", `node ${provider}`,
      "请从 GitHub 仓库安装一个 Skill",
    ])).stdout);
    assert.deepEqual(result.selected, ["installer"]);
    assert.equal(result.confidence, 0.96);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("semantic confidence requires confirmation below the auto-load threshold", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "skill-router-confidence-"));
  try {
    await mkdir(path.join(root, "candidate"));
    await writeFile(path.join(root, "candidate", "SKILL.md"), `---
name: candidate
description: A candidate capability
---
# candidate
`);
    const provider = path.join(root, "provider.mjs");
    await writeFile(provider, 'process.stdin.on("data", () => {}); process.stdin.on("end", () => process.stdout.write(JSON.stringify({selections:[{name:"candidate",confidence:0.7,reason:"uncertain"}]})));');
    const result = JSON.parse((await exec("node", [
      cli, "--skills-dir", root, "route", "--semantic", "--semantic-command", `node ${provider}`,
      "请完成一个候选能力任务",
    ])).stdout);
    assert.equal(result.action, "confirm");
    assert.equal(result.confidence, 0.7);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
