# claw-hermes 🦞☤

> **Letta with hands and ears** — a self-hosted AI agent that learns from you and lives in every messenger you already read.

`claw-hermes` is the connective tissue that turns two of the largest open AI assistant projects on GitHub into a single **personal AI OS**:

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** (Python, Nous Research) — closed learning loop: skill autogeneration, FTS5 session memory, Honcho dialectic user modeling, RL trajectory generation
- **[OpenClaw](https://github.com/openclaw/openclaw)** (TypeScript) — multi-channel control plane: ~24 messaging surfaces (iMessage, WhatsApp, WeChat, Matrix, Voice Wake, Live Canvas, …)

Marriage of the two ships **three things no other product currently combines**:

1. **A closed learning loop in production** — the agent gets smarter every week
2. **24-channel native delivery** — iMessage / WA / Telegram / Discord / Slack / WeChat / Matrix / Voice / Canvas / …
3. **Self-hosted, open, MIT** — your trajectories, your memory, your channels, your model choice

Letta has #1 only. ChatGPT/Claude apps have a thin #2 only and are closed. n8n/Zapier have channel reach but no learning self. **Nobody has all three.**

## Why now

| | GitHub stars | Forks | Discord |
|---|---|---|---|
| OpenClaw | 365k | 75k | 174k members |
| Hermes Agent | 119k | 18k | (Nous Research wider) |
| HermesClaw (WeChat-only bridge) | 239 | 20 | — |

The two communities are fragmented across migration tools (`hermes claw migrate` has open bugs; community forks `0xNyk/openclaw-to-hermes` and `TitzMcgie/openclaw-migrate` exist *because* the official path crashes). Cross-channel memory failure, skill-library lock-in, and multi-channel orchestration with one identity are the top-three unmet needs across both communities. HermesClaw proves demand for a bridge — but it's WeChat-only.

`claw-hermes` is the general bridge.

## What v0.1 ships (today)

A working spine and a beachhead use case:

- ✅ Python CLI (`claw-hermes`) — Click-based, MIT, `pip install claw-hermes`
- ✅ Real `gh` integration — fetch PRs, diffs, lists
- ✅ Routing config (YAML) — `event → channels` with urgency tiers
- ✅ Hermes integration — subprocess to `hermes --non-interactive` with deterministic-skeleton fallback
- ✅ OpenClaw integration — HTTP POST to local gateway with dry-run mode
- ✅ Claude Code skill — drop-in at `skill/SKILL.md`
- ✅ Mocked + pure-function unit tests (15 passing) — runs without either upstream installed

The **wedge use case** v0.1 starts with: **GitHub workflow orchestration for OSS maintainers** — PR review, CI alerts, multi-channel digests. v0.2 expands this into the full *AI-slop firewall + maintainer co-pilot* (see [`ROADMAP.md`](ROADMAP.md)).

## Now available in main: slop-classify (preview)

The v0.2 wedge is live on `main` as a preview:

```bash
# Classify a PR as human / ai-slop / ai-assisted-legit
claw-hermes slop-classify owner/repo 42

# Persist the verdict to the local cross-repo signature store
claw-hermes slop-classify owner/repo 42 --record

# Machine-readable output
claw-hermes slop-classify owner/repo 42 --json

# Route the verdict through OpenClaw (uses the pr_review_requested rule)
claw-hermes slop-classify owner/repo 42 --deliver --dry-run
```

The classifier uses Hermes when available (parses a 3-line `LABEL/CONFIDENCE/REASONING` response)
and falls back to a deterministic heuristic that detects emoji-heavy bodies, "As an AI" phrasing,
suspiciously round line counts, mass-rename diffs, hallucinated imports, and zero-test changes
on large PRs. Recorded verdicts populate `~/.claw-hermes/signatures.db` for the v0.3 cross-repo
learning loop.

## What's coming

Read [`ROADMAP.md`](ROADMAP.md) for the v0.2 → v1.0 trajectory. Highlights:

- **v0.2** — `slop-classify` (preview, in main) + cross-repo signature DB; full per-contributor
  Honcho models, GitHub App template, and `claw-hermes verify` still ahead
- **v0.3** — Federation MVP: unified `Event` JSON, `MemoryBroker` wrapping Hermes FTS5+Honcho, OpenClaw events flow back into the canonical store. iMessage remembers Slack.
- **v0.4** — MCP server + client; `fanout()` API for parallel subagents; skill publisher to ClawHub + Hermes
- **v0.5** — Cross-runtime self-improvement: trajectories that span both runtimes auto-synthesize *bridge skills*
- **v1.0** — Hardening, multi-user identity graph, reference deployment

Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for the federation design — Hermes-as-canonical-store, `agentskills.io` `runtimes:` extension, dual MCP positioning.

## Install

```bash
pip install claw-hermes
gh auth status     # confirm gh CLI is authenticated
claw-hermes init   # write default routing config to ~/.claw-hermes/config.yaml
claw-hermes status # see what's wired up
```

Optional, for full functionality:

```bash
pip install hermes-agent
npm install -g openclaw && openclaw onboard --install-daemon
```

## Usage

```bash
# Show what's wired
claw-hermes status

# See where a GitHub event would go
claw-hermes route ci_failed

# Fetch a PR (uses gh)
claw-hermes pr-fetch torvalds/linux 1

# Generate a PR review digest
claw-hermes pr-review owner/repo 42

# Generate a review and route through OpenClaw (dry-run shows targets without sending)
claw-hermes pr-review owner/repo 42 --deliver --dry-run
claw-hermes pr-review owner/repo 42 --deliver           # actually deliver

# Classify a PR for AI-slop (v0.2 preview)
claw-hermes slop-classify owner/repo 42 --record
```

## Configuration

Default config lives at `~/.claw-hermes/config.yaml`. See [`examples/routing.example.yaml`](examples/routing.example.yaml).

Routing rules look like:

```yaml
routes:
  - event: ci_failed
    channels: [imessage, telegram]
    urgency: urgent
  - event: pr_opened
    channels: [slack]
    urgency: normal
  - event: daily_digest
    channels: [email, telegram]
    urgency: digest
```

## Claude Code skill

This repo ships a Claude Code skill at [`skill/SKILL.md`](skill/SKILL.md):

```bash
mkdir -p ~/.claude/skills/claw-hermes
cp -r skill/* ~/.claude/skills/claw-hermes/
```

## Authoring skills (v0.2)

claw-hermes ships an `agentskills.io` v1.0 manifest schema with a `runtimes:` extension, plus a linter and scaffolder:

```bash
claw-hermes skill new my-skill --runtime both \
  --description "Description >=50 chars describing when to invoke the skill." \
  --author "Your Name"
claw-hermes skill lint my-skill/
claw-hermes skill list ./skills/
```

See [`docs/manifest.md`](docs/manifest.md) for the full schema, every lint code, and a dual-runtime example. A minimal valid skill lives at [`examples/skills/hello-world/`](examples/skills/hello-world/).

## Honest v0.1 scope

| Capability | v0.1 status |
|---|---|
| `gh` CLI integration | ✅ Real, tested |
| Routing config + decision logic | ✅ Real, unit-tested |
| Hermes subprocess integration | ✅ Wired, mocked-tested |
| Hermes graceful degradation (skeleton fallback) | ✅ Real |
| OpenClaw HTTP integration (dry-run + delivery) | ✅ Wired, dry-run-tested |
| OpenClaw gateway probe | ✅ Real |
| **Real end-to-end Telegram/iMessage delivery** | ⏳ Requires OpenClaw daemon — operator-tested only |
| Slop classifier (heuristic + Hermes) | ✅ Preview in main (v0.2) |
| Cross-repo signature store (SQLite) | ✅ Preview in main (v0.2) |
| Federated memory broker | ⏳ v0.3 |
| MCP server + client | ⏳ v0.4 |
| Cross-runtime skill autogen | ⏳ v0.5 |

> **Honesty note:** v0.1 is wiring + scaffold + one beachhead workflow. The "personal AI OS" is the trajectory, not the v0.1 deliverable. Don't `pip install` expecting the full vision today — install if you're a maintainer who wants the GitHub piece, or a contributor who wants to help build the federation layer.

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

All tests are mocked or pure-function — `pytest` requires neither Hermes nor OpenClaw installed.

## Architecture

```
claw_hermes/
├── cli.py         # Click CLI — entry points
├── config.py      # YAML config + dataclass schema
├── router.py      # Pure-function event → channel routing
├── github.py      # `gh` CLI subprocess wrapper
├── hermes.py      # Hermes integration (with deterministic fallback)
├── openclaw.py    # OpenClaw gateway HTTP client (with dry-run mode)
├── slop.py        # AI-slop PR classifier (Hermes + heuristic fallback)
└── signatures.py  # Cross-repo signature SQLite store
```

The bridge is intentionally thin. It does not reimplement either upstream — it composes them. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the v1.0 federation design.

## Contributing

This is going to take a community. Issues open for:

- v0.2 slop-classify implementation
- v0.3 `MemoryBroker` schema design
- v0.4 MCP resource modelling
- agentskills.io `runtimes:` standard extension
- New channel adapters (every messenger you wish your agent lived in)

If you maintain an OSS project drowning in AI-slop PRs, please open an issue describing your workflow — v0.2 is for you.

## License

MIT — see [LICENSE](LICENSE).

## Related

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — the learning loop side
- [OpenClaw](https://github.com/openclaw/openclaw) — the delivery side
- [HermesClaw](https://github.com/AaronWong1999/hermesclaw) — community WeChat-only bridge that proved demand
- [agentskills.io](https://agentskills.io) — open skills standard both upstreams support
- [Letta / MemGPT](https://github.com/letta-ai/letta) — agent memory layer (the closest non-channel competitor)
