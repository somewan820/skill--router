import { spawn } from "node:child_process";
/**
 * Generic host-model bridge.
 *
 * Input:
 *   { task, candidates: [{name, description, ...}] }
 * Output:
 *   { selections: [{name, confidence, reason}] }
 *
 * The command is configured by the host Agent. The Router does not know which
 * model, vendor, or protocol is behind it.
 */
export class StdioSemanticProvider {
    command;
    timeoutMs;
    constructor(command, timeoutMs = 15_000) {
        this.command = command;
        this.timeoutMs = timeoutMs;
    }
    async rank(task, candidates) {
        return new Promise((resolve, reject) => {
            const child = spawn(this.command, { shell: true, stdio: ["pipe", "pipe", "pipe"] });
            let stdout = "";
            let stderr = "";
            const timer = setTimeout(() => {
                child.kill();
                reject(new Error("semantic provider timed out"));
            }, this.timeoutMs);
            child.stdout.on("data", (chunk) => stdout += chunk.toString());
            child.stderr.on("data", (chunk) => stderr += chunk.toString());
            child.on("error", (error) => {
                clearTimeout(timer);
                reject(error);
            });
            child.on("close", (code) => {
                clearTimeout(timer);
                if (code !== 0) {
                    reject(new Error(stderr.trim() || `semantic provider exited with ${code}`));
                    return;
                }
                try {
                    const payload = JSON.parse(stdout);
                    const selections = Array.isArray(payload) ? payload : payload.selections;
                    resolve(Array.isArray(selections) ? selections.filter(validCandidate) : []);
                }
                catch (error) {
                    reject(error);
                }
            });
            child.stdin.end(JSON.stringify({ task, candidates }));
        });
    }
}
function validCandidate(value) {
    if (!value || typeof value !== "object")
        return false;
    const candidate = value;
    return typeof candidate.name === "string"
        && typeof candidate.confidence === "number"
        && typeof candidate.reason === "string";
}
