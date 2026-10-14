import { readFile } from "node:fs/promises";
import path from "node:path";
export async function verify(root) {
    const errors = [];
    try {
        const manifest = JSON.parse(await readFile(path.join(root, "skill.json"), "utf8"));
        for (const field of ["schema_version", "id", "name", "version", "description"])
            if (!manifest[field])
                errors.push(`skill.json missing ${field}`);
    }
    catch {
        errors.push("invalid or missing skill.json");
    }
    try {
        if (!(await readFile(path.join(root, "SKILL.md"), "utf8")).startsWith("---"))
            errors.push("SKILL.md is missing YAML frontmatter");
    }
    catch {
        errors.push("missing SKILL.md");
    }
    return errors;
}
