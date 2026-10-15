import { appendFile, mkdir } from "node:fs/promises";
import path from "node:path";
export function feedbackPath(file) {
    return file || process.env.SKILL_ROUTER_FEEDBACK || path.join(process.env.HOME || ".", ".config", "skill-router", "feedback.jsonl");
}
export async function recordFeedback(record, file) {
    const target = feedbackPath(file);
    await mkdir(path.dirname(target), { recursive: true });
    await appendFile(target, JSON.stringify({ ...record, timestamp: new Date().toISOString() }) + "\n", "utf8");
    return target;
}
