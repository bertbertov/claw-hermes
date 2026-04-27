---
name: claw-hermes
description: Bridges Hermes Agent (closed learning loop, FTS5, Honcho) and OpenClaw (~24 channels, Voice Wake, Live Canvas) into one personal AI OS. Use when the user wants to (1) review PRs / triage issues / classify AI-slop on GitHub repos, (2) push events to messaging channels (Telegram, WhatsApp, iMessage, Discord, Slack, Matrix, WeChat, …), (3) bridge memory between channels (iMessage remembers Slack), or (4) ask "is there a way to use Hermes and OpenClaw together?" — claw-hermes is that bridge.
version: 0.2.0
license: MIT
author: Albert Kamalov
agentskills_version: "1.0"
runtimes:
  hermes:
    entrypoint: python -m claw_hermes.cli
    capabilities: [github, memory.recall, memory.write, subprocess]
  openclaw:
    entrypoint: claw-hermes
    capabilities: [github, channels.send, network]
  both:
    requires_capabilities: [github, memory.recall, channels.send]
keywords: [github, agent, hermes, openclaw, automation, messaging, ai]
homepage: https://github.com/bertbertov/claw-hermes
---

# claw-hermes — personal AI OS bridge

`claw-hermes` is the connective tissue between two of the largest open AI assistant projects:

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** (Python, Nous Research, 119k stars) — closed learning loop, skill autogeneration, FTS5 session memory, Honcho dialectic user modelling, RL trajectory generation
- **[OpenClaw](https://github.com/openclaw/openclaw)** (TypeScript, 365k stars, 174k Discord) — ~24 channel surfaces incl. iMessage, WhatsApp, WeChat, Matrix, Voice Wake, Live Canvas

Tagline: **"Letta with hands and ears."**

The thesis: a self-hosted agent that learns from you AND lives in every messenger you read. No other product (open or closed) currently combines a closed learning loop + 24-channel native delivery + self-hostable.

## When to invoke this skill

- "review PR 123 in <repo>"
- "classify this PR as slop or legit"
- "give me a digest of open PRs in <repo>"
- "what channels would a CI failure route to?"
- "send the latest release notes to my team across iMessage and Slack"
- "can I use Hermes and OpenClaw together?"
- Any GitHub event → messaging channel orchestration question
- Any question about marrying Hermes + OpenClaw

## Prerequisites

```bash
pip install claw-hermes
gh auth status     # gh CLI must be authenticated
```

Optional but recommended for full functionality:
- `pip install hermes-agent` — enables real PR reviews (otherwise a deterministic skeleton is used)
- `npm i -g openclaw && openclaw onboard --install-daemon` — enables real channel delivery

## Core commands (v0.1)

| Command | What |
|---|---|
| `claw-hermes init` | Write default routing config to `~/.claw-hermes/config.yaml` |
| `claw-hermes status` | Show wiring: gh auth, hermes availability, OpenClaw reachability |
| `claw-hermes route <event>` | Show which channels a GitHub event would route to |
| `claw-hermes pr-fetch <repo> <pr#>` | Fetch a PR via `gh` (read-only) |
| `claw-hermes pr-review <repo> <pr#>` | Generate a review digest (uses Hermes if installed) |
| `claw-hermes pr-review <repo> <pr#> --deliver --dry-run` | Show channel routing without firing |
| `claw-hermes hermes-probe` | Read-only Hermes availability check |
| `claw-hermes openclaw-probe` | Read-only OpenClaw gateway HTTP probe |

## v0.2 commands (shipped)

| Command | What |
|---|---|
| `claw-hermes skill lint <path>` | Validate a SKILL.md manifest (file or directory of skills) against agentskills.io v1.0 + the `runtimes:` extension |
| `claw-hermes skill new <name>` | Scaffold a new dual-runtime skill at `<name>/SKILL.md` and lint it automatically |
| `claw-hermes skill list <dir>` | Discover all `*/SKILL.md` skills under a directory and print a one-line summary each |

## Coming in v0.3

| Command | What |
|---|---|
| `claw-hermes slop-classify <pr-url>` | Classify a PR as human / ai-slop / ai-assisted-legit (cross-repo learned signatures) |
| `claw-hermes triage <repo>` | Per-contributor model surfaces "this contributor's last 5 PRs all merged" |
| `claw-hermes verify` | Walk every pipeline stage; refuse to claim success without terminal-channel ack |

## Workflow patterns

### Pattern: review-then-route
1. `claw-hermes pr-review <repo> <pr#>` to generate a digest
2. Pipe to `--deliver --dry-run` first so the user sees where it would go
3. Drop `--dry-run` once they confirm

### Pattern: status-before-anything
Always run `claw-hermes status` before claiming a delivery worked — it reports whether OpenClaw is actually reachable. **Don't trust silence.**

### Pattern: graceful degradation
If Hermes isn't installed, the review falls back to a deterministic skeleton with PR metadata. Tell the user this happened so they can install Hermes if they want the AI review.

## Verification before claiming done

`claw-hermes` itself codifies a verify-end-to-end rule. After any delivery, check the `delivered_to` and `failed` fields in the output. **Don't say "sent" just because the command exited 0** — `dry_run=True` always exits 0 even though no message left the box.

## Skill provenance + roadmap

This skill ships with the [`claw-hermes`](https://github.com/bertbertov/claw-hermes) repo at `skill/SKILL.md`. To install:

```bash
mkdir -p ~/.claude/skills/claw-hermes
cp -r /path/to/claw-hermes/skill/* ~/.claude/skills/claw-hermes/
```

For the v0.2 → v1.0 trajectory (federation, MCP, cross-runtime self-improvement), see [`ROADMAP.md`](https://github.com/bertbertov/claw-hermes/blob/main/ROADMAP.md). For the federation design, see [`ARCHITECTURE.md`](https://github.com/bertbertov/claw-hermes/blob/main/ARCHITECTURE.md).
