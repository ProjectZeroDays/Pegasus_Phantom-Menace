# Vendored: ruflo agent/skill library

Trimmed copy of the parts of [ruflo](https://github.com/ruvnet/ruflo) that are reusable
as a reference library for Pegasus agents. Everything else (CLI core, crates, v3,
plugins, docs, tests, verification harness, build config) was pruned.

- **Upstream:** https://github.com/ruvnet/ruflo
- **Fork used:** https://github.com/projectzerodays/ruflo
- **Commit:** `6051f6702b610e1101e727ccffd5f379f75ea6fc`
- **License:** MIT, Copyright (c) 2024-2026 ruvnet — see `LICENSE`
- **Size:** 468 files / ~3.3 MB (upstream snapshot was ~196 MB)

## What is kept

| Path | Contents |
| --- | --- |
| `.claude/agents/` | 108 agent definitions (markdown, front-matter + prompt) |
| `.claude/skills/` | 42 skill definitions |
| `.claude/commands/` | 168 slash commands |
| `.claude/workflows/` | 3 workflow JS files |
| `.agents/skills/` | 143 skill definitions in the `.agents` format |
| `skills.sh.json` | Skill grouping/index manifest |
| `AGENTS.md`, `SKILL.md` | Upstream authoring conventions and skill spec |

## What was pruned

`crates/`, `v3/`, `plugins/`, `ruflo/`, `docs/`, `bin/`, `data/`, `scripts/`,
`tests/`, `verification/`, `.github/`, `.githooks/`, `.harness/`,
`.claude-plugin/`, `.claude/helpers/`, `.claude/checkpoints/`,
`.claude/settings.json*`, `.claude/mcp.json`, `package*.json`, `pnpm-lock.yaml`,
`Cargo.toml`, `tsconfig.json`, `agentdb.rvf*`, `ruflo-plugins.gif`.

## Using it

These are plain markdown definitions, so they can be copied into a project-local
`.claude/`, `.opencode/`, or `.agents/` directory when a session needs them.
They are **not** imported by `pegasus.modules.agents` at runtime — that module is
Pegasus's own bridge. Nothing here executes as part of the app.

## Attribution

Content is unmodified from the commit above. Do not relicense it; keep the MIT
notice with any redistribution. Upstream is the authority for updates — re-vendor
from a newer commit rather than patching in place.
