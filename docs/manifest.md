# Skill manifest schema (v0.2)

> agentskills.io v1.0 + the `runtimes:` extension.

A skill manifest is a Markdown file (`SKILL.md`) with YAML frontmatter delimited by `---` lines. The frontmatter declares dual-runtime metadata; the body is the human-facing skill description.

claw-hermes ships a linter (`claw-hermes skill lint`) and a scaffolder (`claw-hermes skill new`) so you don't have to write manifests from memory.

## Minimal example

```yaml
---
name: hello-world
description: Minimal valid dual-runtime skill that prints a greeting in either Hermes or OpenClaw. Use when verifying a freshly-installed claw-hermes setup.
version: 0.1.0
license: MIT
author: claw-hermes contributors
agentskills_version: "1.0"
runtimes:
  hermes:
    entrypoint: python -c "print('hello from hermes')"
  openclaw:
    entrypoint: node -e "console.log('hello from openclaw')"
  both:
    requires_capabilities: []
---

# hello-world

The smallest possible dual-runtime skill...
```

See `examples/skills/hello-world/SKILL.md` for the full file.

## Frontmatter fields

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Slug, `^[a-z][a-z0-9-]{2,49}$` (lowercase, hyphens, 3–50 chars) |
| `description` | yes | 50–500 chars; describes when to invoke the skill |
| `version` | yes | Valid semver (`0.1.0`, `1.2.3-alpha.1`) |
| `license` | yes | SPDX id; warning if not in known list |
| `author` | yes | Free-text |
| `agentskills_version` | yes | Currently only `"1.0"` is supported in v0.2 |
| `runtimes` | yes | At least one of `hermes`, `openclaw`, `both` (see below) |
| `keywords` | no | List of strings |
| `homepage` | no | URL |

Any unknown top-level field is treated as an advisory ClawHub extension and emits a `clawhub.proprietary_field` warning.

## The `runtimes:` block

Three keys are recognised:

- **`hermes`** — how the skill loads inside Hermes Agent (Python). Requires `entrypoint`.
- **`openclaw`** — how the skill loads inside OpenClaw (TypeScript). Requires `entrypoint`.
- **`both`** — optional shared block. Use it to declare `requires_capabilities` that apply across runtimes.

Each runtime block accepts:

| Field | Type | Notes |
|---|---|---|
| `entrypoint` | string | Required for `hermes` and `openclaw`; the command the runtime should execute. |
| `capabilities` | list | Capabilities the skill **uses**. Unknown values warn. |
| `requires_capabilities` | list | Capabilities the skill **requires** the runtime to provide (used inside the `both:` block). |

### Known capabilities

```
github
memory.recall
memory.write
channels.send
channels.receive
subprocess
network
filesystem.read
filesystem.write
```

## Lint codes

Each rule has a stable `code` so callers can render or filter without parsing free-text messages.

| Code | Level | Meaning |
|---|---|---|
| `frontmatter.missing` | error | File has no `---` frontmatter delimiters. |
| `frontmatter.invalid_yaml` | error | Frontmatter is not parseable as a YAML mapping. |
| `name.missing` | error | `name` is absent. |
| `name.format` | error | `name` does not match the slug pattern. |
| `description.missing` | error | `description` is absent. |
| `description.too_short` | error | `description` is shorter than 50 chars. |
| `description.too_long` | error | `description` is longer than 500 chars. |
| `version.missing` | error | `version` is absent. |
| `version.format` | error | `version` is not valid semver. |
| `license.missing` | error | `license` is absent. |
| `license.unknown` | warning | `license` is not in the known SPDX list. |
| `author.missing` | error | `author` is absent. |
| `agentskills_version.missing` | error | `agentskills_version` is absent. |
| `agentskills_version.unsupported` | error | Only `"1.0"` is accepted in v0.2. |
| `runtimes.missing` | error | The `runtimes:` block is absent. |
| `runtimes.empty` | error | No runtime declared (need at least one of hermes / openclaw / both). |
| `runtimes.unknown_key` | warning | Anything other than `hermes`, `openclaw`, or `both`. |
| `runtime.entrypoint.missing` | error | `hermes` or `openclaw` block has no `entrypoint`. |
| `runtime.capabilities.unknown` | warning | A capability outside the known set. |
| `body.missing` | error | The Markdown body is empty. |
| `body.too_short` | error | The Markdown body is shorter than 200 chars. |
| `clawhub.proprietary_field` | warning | Any unknown top-level field — treated as advisory ClawHub extension. |
| `file.missing` | error | The path passed to `lint` does not exist. |

## CLI

```bash
# Lint a single skill or a directory of skills.
claw-hermes skill lint skill/
claw-hermes skill lint examples/skills/hello-world/
claw-hermes skill lint . --strict     # warnings become errors
claw-hermes skill lint . --json       # machine-readable

# Scaffold a new dual-runtime skill (auto-lints after writing).
claw-hermes skill new my-skill \
  --runtime both \
  --description "Description >=50 chars describing when to invoke the skill." \
  --author "Your Name"

# Discover and summarise skills in a directory.
claw-hermes skill list ./skills/
```

### Exit codes

| Exit | Meaning |
|---|---|
| 0 | Clean (or warnings only with no `--strict`). |
| 1 | Warnings only. |
| 2 | At least one error, or warnings under `--strict`. |

## Dual-runtime example

```yaml
---
name: slop-classify
description: Classify a PR as human / ai-slop / ai-assisted-legit using cross-repo learned signatures. Use when an OSS maintainer asks whether a PR is genuine or low-effort AI output.
version: 0.2.0
license: MIT
author: claw-hermes contributors
agentskills_version: "1.0"
runtimes:
  hermes:
    entrypoint: python -m clawhermes.skills.slop_classify
    capabilities: [github, memory.recall, memory.write]
  openclaw:
    entrypoint: node ./dist/slop_classify.js
    capabilities: [github, channels.send]
  both:
    requires_capabilities: [github, memory.recall]
keywords: [github, pr, slop, classification]
homepage: https://github.com/bertbertov/claw-hermes
---

# slop-classify

...
```

The shared `both:` block is the integration contract: the runtime that loads the skill must provide every capability listed in `requires_capabilities`. Each per-runtime block declares the capabilities the skill itself **uses** when running inside that runtime.

## v0.3 outlook

- JSON Schema export (`claw-hermes skill schema --json`) for IDE integration.
- Signed manifests (sigstore / minisign) — supply-chain hygiene for ClawHub.
- `claw-hermes skill publish` — dual-pushes to ClawHub and the Hermes skill table.
- Upstream the `runtimes:` block to agentskills.io proper.
