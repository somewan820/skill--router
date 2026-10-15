---
name: skill-router
description: Discover, select, compose, and route Agent Skills based on the user's task, resource type, domain, and requested operation. Use when a task may require a specialized local or external Skill, such as Feishu documents, spreadsheets, code review, deployment, or other domain-specific workflows.
---

# Skill Router

Use this Skill as a local-first routing layer before starting a specialized task.

## Routing policy

1. Read the current routing mode: `auto`, `manual`, or `off`.
2. Prefer Skills already installed in the current Agent environment.
3. Match both the resource type and requested operation.
4. Select multiple Skills when the task crosses domains.
5. Do not force a low-confidence match.
6. Search external registries only when local Skills are insufficient and external search is enabled.
7. Never install an external Skill without explicit user confirmation.
8. Explain which Skills were selected and why.

## Modes

- `auto`: inspect the task and select local Skills automatically.
- `manual`: use only Skills explicitly named by the user.
- `off`: do not automatically discover or load Skills.

The host Agent should persist the mode in its own configuration. A single request may override the persistent mode.

## Runtime

When Node.js is available, use the bundled runtime:

```bash
node dist/cli.js route "USER_TASK"
```

Use `--mode manual --use SKILL_NAME` for explicit selection. Use `--mode off` to bypass routing.

The runtime returns JSON containing selected Skills, confidence, reasons, and an execution plan. Load the selected Skills only after reviewing that result.

When descriptions are not enough for deterministic matching, the host Agent may provide a semantic ranking command with `--semantic-command`. The command receives a JSON task plus candidate metadata on stdin and must return JSON selections with `name`, `confidence`, and `reason`. Do not treat semantic results as permission to install external Skills.

When the user corrects a route, record the correction with the runtime `feedback` command so it can become a future regression case. Feedback is local-only unless the host Agent explicitly exports it.

## Installation safety

When this Skill is provided as a repository URL:

1. Read `skill.json`, `SKILL.md`, and `INSTALL.md` before executing anything.
2. Show the user the requested permissions and installation destination.
3. Ask for confirmation before writing to an Agent Skill directory.
4. Prefer copying the package into the host's supported Skill directory.
5. Run the verification command after installation.
6. Do not automatically install third-party Skills discovered by this router.

