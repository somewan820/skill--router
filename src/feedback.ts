import { appendFile, mkdir } from "node:fs/promises";
import path from "node:path";

export interface FeedbackRecord {
  task: string;
  selected: string[];
  accepted: boolean;
  corrected?: string[];
  timestamp: string;
}

export function feedbackPath(file?: string): string {
  return file || process.env.SKILL_ROUTER_FEEDBACK || path.join(process.env.HOME || ".", ".config", "skill-router", "feedback.jsonl");
}

export async function recordFeedback(
  record: Omit<FeedbackRecord, "timestamp">,
  file?: string,
): Promise<string> {
  const target = feedbackPath(file);
  await mkdir(path.dirname(target), { recursive: true });
  await appendFile(target, JSON.stringify({ ...record, timestamp: new Date().toISOString() }) + "\n", "utf8");
  return target;
}
