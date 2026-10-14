import { readFile } from "node:fs/promises";
import path from "node:path";
function listValue(value) {
    if (Array.isArray(value))
        return value.map(String);
    return value == null ? [] : [String(value)];
}
function frontmatter(text) {
    if (!text.startsWith("---"))
        return {};
    const body = text.split("---", 3)[1] ?? "";
    const result = {};
    for (const line of body.split(/\r?\n/)) {
        const separator = line.indexOf(":");
        if (separator < 0 || line.trim().startsWith("#"))
            continue;
        const key = line.slice(0, separator).trim();
        const raw = line.slice(separator + 1).trim();
        if (raw.startsWith("[") && raw.endsWith("]")) {
            result[key] = raw.slice(1, -1).split(",").map((item) => item.trim().replace(/^['"]|['"]$/g, "")).filter(Boolean);
        }
        else {
            result[key] = raw.replace(/^['"]|['"]$/g, "");
        }
    }
    return result;
}
export async function parseSkill(file) {
    try {
        const data = frontmatter(await readFile(file, "utf8"));
        const name = String(data.name || path.basename(path.dirname(file)));
        const description = String(data.description || "").trim();
        if (!name || !description)
            return undefined;
        return {
            name,
            description,
            source: "local",
            location: path.dirname(file),
            domains: listValue(data.domains),
            resource_types: listValue(data.resource_types),
            operations: listValue(data.operations),
            triggers: listValue(data.triggers),
            not_for: listValue(data.not_for),
            related_skills: listValue(data.related_skills),
            dependencies: listValue(data.dependencies),
            exclusive_group: data.exclusive_group ? String(data.exclusive_group) : undefined,
            priority: Number(data.priority || 0),
            version: data.version ? String(data.version) : undefined,
        };
    }
    catch {
        return undefined;
    }
}
