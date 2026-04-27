# claw-hermes Roadmap

> The trajectory from "GitHub workflow scaffold" to "personal AI OS."

## North star

> A self-hosted AI agent that **learns from you** (Hermes) and **lives in every messenger you already read** (OpenClaw), with a single canonical memory and skill registry across both runtimes.

## Versions

### v0.1 — The wiring (shipped)

**Goal:** prove the marriage works at the CLI level. Ship a thin Python orchestrator with graceful degradation.

- ✅ Python package + Click CLI
- ✅ `gh` CLI integration (real)
- ✅ Routing config (YAML) with urgency tiers
- ✅ Hermes subprocess integration with deterministic-skeleton fallback
- ✅ OpenClaw HTTP integration with dry-run mode
- ✅ 15 mocked / pure-function tests
- ✅ Claude Code skill (drop-in at `skill/SKILL.md`)
- ✅ MIT license, public repo

### v0.2 — The maintainer wedge (4 weeks)

**Goal:** ship a beachhead use case that solves an *acute, dated* pain — AI-slop on OSS PRs (curl killed bug bounties Jan 2026; OpenSSF issue #178 actively asks for this; Stenberg/Jazzband/Godot maintainers publicly burning out).

- `claw-hermes slop-classify <pr-url>` — classifies PRs as `human` / `ai-slop` / `ai-assisted-legit` with confidence + signature
- Cross-repo learning — every `--reject` / `--merge` decision trains shared signatures (the moat GitHub structurally won't replicate)
- Per-contributor model via Honcho — surfaces "this contributor's last 5 PRs all merged"
- Multi-channel digest (Slack/Discord/Matrix) of slop-quarantined queue
- GitHub App template (`/install`) for one-click subscription
- `claw-hermes verify` — walks every pipeline stage, refuses to report success without terminal-channel ack (codifying verify-end-to-end into the bridge itself)
- ✅ **v0.2-preview shipped on `feat/v0.2-federation-event-bus`:** unified `Event` type, `MemoryBroker` Protocol with a SQLite + FTS5 default, async WebSocket bus skeleton (`bus serve` / `bus emit`), `memory record-test` / `memory show` CLI. Federation end-to-end (`MemoryBroker` over Hermes' FTS5 + Honcho, OpenClaw events flowing into the canonical store) is still v0.3.

**Distribution:** seed in r/LocalLLaMA, Nous Research Discord, OpenClaw "Friends of the Crustacean" Discord, OpenSSF working group, OSS maintainer Twitter.

### v0.3 — Federation MVP (6 weeks)

**Goal:** make the marriage *internal*, not just CLI-level. iMessage remembers Slack.

- ✅ Unified `Event` type (NDJSON over WebSocket between Gateway and Core) — *shipped as v0.2-preview*
- ✅ `MemoryBroker` Protocol — *interface shipped as v0.2-preview with SQLite default; v0.3 replaces it with a direct wrapper over Hermes' FTS5 + Honcho so Hermes becomes canonical and OpenClaw a writer-client*
- `clawhermes skill lint` — validates dual-runtime manifests (`agentskills.io` extended with `runtimes: [hermes, openclaw, both]`)
- OS-keychain auth vault (Keychain / Credential Manager / libsecret)
- Replace v0.1 subprocess calls with the bus
- Federation end-to-end: an OpenClaw inbound message records into the canonical store and is recallable from a Hermes session keyed on `user_identity_id`, not `channel_id` — *the iMessage-remembers-Slack acceptance test*

### v0.4 — MCP + fan-out (8 weeks)

**Goal:** be addressable from any MCP client (Claude Desktop, Cursor, Cline) and parallelise across both runtimes.

- claw-hermes as an **MCP server** — exposes memory, channels, GitHub events as resources/tools
- claw-hermes as an **MCP client** of Hermes and OpenClaw — consumes their tool surfaces
- `fanout()` API — Hermes spawns N subagents, results funnel through OpenClaw routing. Hermes owns *compute* fan-out; OpenClaw owns *delivery* fan-out.
- Skill publisher CLI — `claw-hermes skill publish` dual-pushes to ClawHub + Hermes registry
- Honcho theory-of-mind exposed via MCP resource

### v0.5 — Self-improvement (8 weeks)

**Goal:** the bridge generates its own skills.

- Trajectory schema gains `cross_runtime_signal` flag — set when a trajectory traverses both Gateway and Hermes (e.g., user asks via WA, agent delivers via Slack)
- When the flag fires N times for similar shape, synthesizer emits a *bridge skill* with `runtimes: both`, runs the linter, and registers it
- age-encrypted portable secrets vault
- Pip package with vendored Gateway binary (one-command install)
- Homebrew + scoop formulae

### v1.0 — Hardening + GTM (8 weeks)

**Goal:** production-ready, contributable, growing.

- Protobuf wire format (NDJSON optional)
- OpenTelemetry spans across both runtimes (debuggability)
- Audit log of every cross-runtime call
- Signed skill manifests (supply-chain hygiene)
- Multi-user identity graph (family / team accounts on one host with isolated Honcho profiles)
- Reference deployment (Docker compose, Tailscale-fronted)
- Launch in r/LocalLLaMA + Nous Discord + Friends-of-the-Crustacean Discord + Hacker News simultaneously

## Use case expansion path

After v0.2 (maintainer wedge) ships and earns trust, the same Honcho profile primitive scales. Each step reuses the prior step's customer or infrastructure:

1. **OSS maintainer assistant** (v0.2) — slop firewall + contributor modeling. Same buyer.
2. **Solo-founder support proxy** — Hermes drafts Gmail/Slack/Discord support replies in the founder's voice (RL-learned from sent folder). Same Honcho mechanism, new buyer.
3. **Founder ops co-pilot** — once support, GitHub, and Stripe are wired, the morning voice brief is a free expansion. ARPU 5×s; Honcho profile becomes load-bearing.
4. **Group-chat brain** — drop into any WA/Telegram/Discord group, indexes scrollback, surfaces "what did we decide about X." First consumer wedge; viral seeding.

We do not pivot to consumer until B2B-dev gives us trust + cash flow.

## Risks (architectural)

1. **Hermes' DB schema changes break the broker.** Mitigation: Hermes pinned via git submodule with a contract-test suite that runs on every Hermes bump.
2. **Gateway/Core split-brain on event ordering.** Mitigation: monotonic ULID `event_id`, idempotent writes, single-writer rule (Hermes is the only writer to the canonical store).
3. **Skill manifest fragmentation between agentskills.io and ClawHub.** Mitigation: claw-hermes upstreams the `runtimes:` block to agentskills.io in v0.3; ClawHub extensions treated as advisory.

## Risks (strategic)

1. **OpenAI/Anthropic ship native iMessage/WhatsApp connectors with Memory.** Mitigation: lean into self-hosted + privacy + the channels they refuse (WeChat/Matrix/Signal/Voice).
2. **Letta or another OSS memory project ships 24-channel adapters.** Mitigation: make the channel UX deep (Live Canvas, Voice Wake, iMessage threading) — adapters alone won't replicate.
3. **Nous Research absorbs the bridge into Hermes core.** This is fine — the goal is the marriage existing, not who owns it. Stay close to Nous; offer to upstream when the time comes.

## How to help

If you maintain an OSS project drowning in AI-slop PRs — open an issue describing your workflow. v0.2 is for you.

If you build agents — read [`ARCHITECTURE.md`](ARCHITECTURE.md) and PR the `Event` type, `MemoryBroker`, or `runtimes:` extension.

If you run Hermes or OpenClaw — try v0.1, file every friction point. The bridge is only as good as the integration evidence.
