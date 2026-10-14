# Agent Installation Protocol

This repository is a portable Agent Skill package. An Agent receiving this repository URL should follow this protocol rather than assuming a vendor-specific directory.

## Protocol

1. Inspect `skill.json`, `SKILL.md`, and this file.
2. Check that the host Agent can load Markdown Skills.
3. Determine the host's supported Skill directory. Prefer a project-local directory when the user asks for a project-only installation; otherwise use the host's documented user Skill directory.
4. Show the user:
   - package id and version;
   - files to be written;
   - requested permissions;
   - whether the optional Node.js runtime is available.
5. Ask for explicit confirmation before writing files.
6. Install this repository as `<skill-directory>/skill-router/`.
7. Do not run arbitrary repository scripts before reviewing them.
8. Run `node dist/cli.js verify --path <installed-path>` if Node.js is available.
9. Report the installed path, enabled capabilities, and any unavailable optional features.

The installer writes an installation record. Updates replace only files managed by this package. Uninstallation refuses directories without that record and preserves files added by the user.

## Reference installer

From the repository root, after user confirmation:

```bash
npm install
npm run build
node dist/cli.js install \
  --destination "$AGENT_SKILL_DIRECTORY/skill-router" \
  --approve
```

To preview or confirm removal:

```bash
node dist/cli.js uninstall \
  --destination "$AGENT_SKILL_DIRECTORY/skill-router"
node dist/cli.js uninstall \
  --destination "$AGENT_SKILL_DIRECTORY/skill-router" \
  --approve
```

Preview without changing files by omitting `--approve` from the reference install command.

The reference installer never chooses a vendor-specific directory automatically. The host Agent supplies the destination it supports.

