import { readFile, writeFile } from "node:fs/promises";
import { performance } from "node:perf_hooks";
import { SkillRouter } from "../dist/router.js";

const catalog = [
  {name:"code-review", description:"Review code changes for security regressions", operations:["review"], triggers:["代码审查","代码变更","安全","回归","code review","diff"], exclusive_group:"reviewer"},
  {name:"issue-tracker", description:"Create and update project issues", operations:["create_issue"], triggers:["创建工单","问题","ticket","issue"]},
  {name:"test-runner", description:"Run automated tests and inspect failures", operations:["test"], triggers:["运行测试","测试失败","test","failing tests"]},
  {name:"deploy", description:"Deploy services to an environment", operations:["deploy"], triggers:["部署","发布","deploy","release"]},
  {name:"database", description:"Plan and execute database migrations", operations:["migrate"], triggers:["数据库迁移","迁移数据库","migration","schema change"]},
  {name:"docs", description:"Write and update technical documentation", operations:["write"], triggers:["技术文档","接口文档","documentation","README"]},
  {name:"exporter", description:"Export a final report artifact", operations:["export"], triggers:["导出报告","export report"], dependencies:["code-review"]},
  {name:"dependency-audit", description:"Audit package dependencies for vulnerabilities", operations:["audit"], triggers:["依赖漏洞","依赖审计","dependency audit","vulnerability"]},
];

const tasks = JSON.parse(await readFile(new URL("./tasks.json", import.meta.url), "utf8"));
const router = new SkillRouter({list: async () => catalog, search: async () => catalog});

function mean(values) { return values.reduce((a, b) => a + b, 0) / values.length; }
function quantile(values, q) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * q))];
}
function metricFor(expected, actual) {
  const e = new Set(expected), a = new Set(actual);
  const tp = [...a].filter((item) => e.has(item)).length;
  const fp = [...a].filter((item) => !e.has(item)).length;
  const fn = [...e].filter((item) => !a.has(item)).length;
  return {tp, fp, fn, exact: expected.length === actual.length && tp === expected.length};
}
function summarize(rows) {
  const totals = rows.reduce((sum, row) => ({
    tp: sum.tp + row.tp, fp: sum.fp + row.fp, fn: sum.fn + row.fn,
    exact: sum.exact + Number(row.exact), emptyCorrect: sum.emptyCorrect + Number(row.expected === 0 && row.actual === 0),
  }), {tp: 0, fp: 0, fn: 0, exact: 0, emptyCorrect: 0});
  const precision = totals.tp / (totals.tp + totals.fp || 1);
  const recall = totals.tp / (totals.tp + totals.fn || 1);
  const f1 = 2 * precision * recall / (precision + recall || 1);
  const negatives = rows.filter((row) => row.expected === 0).length;
  const latencies = rows.map((row) => row.latencyMs);
  return {
    tasks: rows.length,
    expectedSelections: rows.reduce((sum, row) => sum + row.expected, 0),
    truePositives: totals.tp,
    falsePositives: totals.fp,
    falseNegatives: totals.fn,
    precision, recall, f1,
    exactPlanAccuracy: totals.exact / rows.length,
    negativeTaskSpecificity: totals.emptyCorrect / (negatives || 1),
    averageSelected: mean(rows.map((row) => row.actual)),
    averageLatencyMs: mean(latencies),
    p95LatencyMs: quantile(latencies, 0.95),
  };
}
function bootstrapF1(rows, iterations = 2000) {
  let seed = 42;
  const random = () => {
    seed = (1664525 * seed + 1013904223) >>> 0;
    return seed / 0x100000000;
  };
  const values = [];
  for (let i = 0; i < iterations; i++) {
    const sample = Array.from({length: rows.length}, () => rows[Math.floor(random() * rows.length)]);
    values.push(summarize(sample).f1);
  }
  return {lower: quantile(values, 0.025), upper: quantile(values, 0.975)};
}

const treatment = [];
for (const task of tasks) {
  const start = performance.now();
  const result = await router.route({text: task.text, max_skills: 4});
  const timing = performance.now() - start;
  const metrics = metricFor(task.expected, result.selected);
  treatment.push({expected: task.expected.length, actual: result.selected.length, latencyMs: timing, ...metrics});
}
const control = tasks.map((task) => ({
  expected: task.expected.length,
  actual: 0,
  latencyMs: 0,
  ...metricFor(task.expected, []),
}));
const report = {
  generatedAt: new Date().toISOString(),
  dataset: {tasks: tasks.length, catalogSkills: catalog.length, source: "evaluation/tasks.json"},
  control: summarize(control),
  treatment: summarize(treatment),
};
report.treatment.f1Bootstrap95 = bootstrapF1(treatment);
report.delta = {
  recall: report.treatment.recall - report.control.recall,
  f1: report.treatment.f1 - report.control.f1,
  exactPlanAccuracy: report.treatment.exactPlanAccuracy - report.control.exactPlanAccuracy,
  negativeTaskSpecificity: report.treatment.negativeTaskSpecificity - report.control.negativeTaskSpecificity,
};
await writeFile(new URL("./results.json", import.meta.url), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report, null, 2));
