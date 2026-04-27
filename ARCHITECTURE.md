# claw-hermes Architecture

> The federation design that turns two assistants into one personal AI OS.

## v1.0 architecture (target)

```
                       ┌──────────────────────────────────┐
                       │       User Surfaces (~24)        │
                       │  iMessage WA TG Slack Discord    │
                       │  WeChat Matrix Voice Canvas …    │
                       └───────────────┬──────────────────┘
                                       │ native protocols
                       ┌───────────────▼──────────────────┐
                       │   OpenClaw Gateway  :18789       │
                       │   Node — channel adapters,       │
                       │   sandbox exec, ClawHub skills   │
                       └───────────────┬──────────────────┘
                                       │ Event JSON over WS
┌──────────────┐   resources/tools     │
│ GitHub / MCP ├───────────┐           │
│   external   │           │           │
└──────────────┘           ▼           ▼
                ┌────────────────────────────────────┐
                │      claw-hermes Core (Python)     │
                │  ┌──────────────────────────────┐  │
                │  │ Event Bus (pub/sub)          │  │
                │  ├──────────────────────────────┤  │
                │  │ Federation Layer             │  │
                │  │   • MemoryBroker             │  │
                │  │   • SkillRegistry            │  │
                │  │   • AuthVault (age + OS kc)  │  │
                │  ├──────────────────────────────┤  │
                │  │ Orchestrator                 │  │
                │  │   • Subagent pool (asyncio)  │  │
                │  │   • Routing rules (YAML+SQL) │  │
                │  │   • MCP server + client      │  │
                │  └──────────────────────────────┘  │
                └────────────┬───────────────────────┘
                             │ stdio / unix socket
                ┌────────────▼───────────────────────┐
                │        Hermes Agent (Python)       │
                │  RL loop, Honcho, subagent spawn,  │
                │  trajectory writer                 │
                └────────────┬───────────────────────┘
                             │
                ┌────────────▼───────────────────────┐
                │   Canonical Store (SQLite + FTS5)  │
                │   sessions, events, embeddings,    │
                │   honcho theory-of-mind, skills    │
                └────────────────────────────────────┘
```

## The 8 architectural decisions

### 1. Memory federation: Hermes is canonical; OpenClaw is a writer-client

Hermes already owns the learning loop, FTS5, Honcho dialectic, and trajectory generation. Duplicating that in claw-hermes or making it a CRDT peer would fork the dataset that Hermes' RL depends on.

claw-hermes exposes a thin `MemoryBroker` API wrapping Hermes' DB:

```python
broker.record_event(event)
broker.recall(query, k=10)
broker.theory_of(user_id) -> HonchoModel
```

The Gateway writes channel events back through it. **iMessage remembers Slack** because both append to the same session graph, keyed by `user_identity_id`, not `channel_id`.

### 2. Skill registry: extend agentskills.io with a `runtimes:` block

Both runtimes already speak `agentskills.io`. Add a `runtimes:` field declaring entrypoints and capability requirements:

```yaml
---
name: slop-classify
description: Classify a PR as human / ai-slop / ai-assisted-legit.
runtimes:
  hermes:
    entrypoint: python -m clawhermes.skills.slop_classify
  openclaw:
    entrypoint: node ./dist/slop_classify.js
  both:
    requires_capabilities: [github, memory.recall]
---
```

Ship `clawhermes skill lint` (validates manifest + dual loadability) and `clawhermes skill publish` (pushes to ClawHub *and* registers with Hermes' skill table). One source tree, two loaders, no fork.

### 3. Unified `Event` type

```json
{
  "event_id": "01HMT...",
  "ts": "2026-04-27T14:02:11Z",
  "kind": "message.inbound",
  "actor": {"id": "user:albert", "channel": "imessage", "handle": "+971..."},
  "session_id": "sess_albert_main",
  "payload": {"text": "did the GLD bot fire?", "attachments": []},
  "context": {"thread_id": "...", "reply_to": null},
  "trace": {"origin": "openclaw.gateway", "span_id": "..."}
}
```

Both runtimes produce and consume this. Wire format: NDJSON over WebSocket between Gateway and Core; protobuf optional in v1.0.

### 4. MCP — both, but asymmetric

claw-hermes is:

- **MCP server** — exposing GitHub events, channel surfaces, and the canonical memory as resources/tools to *external* clients (Claude Desktop, Cursor, Cline)
- **MCP client** — consuming Hermes' agent tools and OpenClaw's channel tools

Bidirectional positioning lets the user talk to claw-hermes from Claude Desktop while Hermes still drives the loop.

### 5. Subagent parallelism: single API, Hermes pool underneath

```python
clawhermes.fanout(
    task="review PR",
    inputs=[pr1, pr2, pr3, pr4, pr5],
    agent="reviewer",
    deliver_to=["slack:#eng", "imessage:albert"]
)
```

`Orchestrator` calls Hermes' subagent spawn 5×; each subagent runs its own trajectory; results funnel through OpenClaw routing. **OpenClaw's multi-agent router handles delivery fan-out; Hermes handles compute fan-out.** No double-orchestration.

### 6. Auth: OS keychain + age-encrypted vault, never plaintext on disk

Tokens live in macOS Keychain / Windows Credential Manager / libsecret, mirrored into an `age`-encrypted `secrets.age` for portability. claw-hermes exposes `auth.get(channel)` returning short-lived in-memory handles; Gateway and Hermes never see the raw secret on disk. Pairing flows (iMessage, WA QR) run in Gateway, hand the resulting token straight to the vault. Rotation is a first-class command.

### 7. Self-improvement: cross-runtime skill synthesis

Hermes' periodic nudge loop already writes skills it discovers it needs. Extend the trajectory schema with a `cross_runtime_signal` flag set when a trajectory traverses both Gateway and Hermes (e.g., "user asks via WA, agent delivers via Slack").

When the flag fires N times for similar shape, the synthesizer emits a *bridge skill* (a manifest with `runtimes: both`), runs the linter, and registers it.

The closed loop becomes:

```
observe cross-channel friction
  → propose skill
    → lint
      → install
        → measure trajectory delta
          → reinforce or revert
```

### 8. Distribution: pip package with bundled Node sidecar

`pip install clawhermes` ships the Core + a vendored Gateway binary (packaged via `pkg` or `bun build --compile`) launched as a subprocess.

Reasons:
1. Hermes is Python and is the heavier of the two; porting it to TS is nine months of wasted work
2. pip + Homebrew formulae are trivial wrappers
3. Hermes-plugin distribution would lock out users who want OpenClaw without Hermes

**One install, two runtimes, one orchestrator.**

## The 3 architectural risks

### 1. Hermes' DB schema changes break the broker

Hermes is research-grade Python from Nous Research; FTS5/Honcho schemas will churn.

**Mitigation:** Hermes pinned via git submodule with a contract-test suite that runs in CI on every Hermes bump and fails loud before users see it. No silent migrations.

### 2. Gateway/Core split-brain on event ordering

Two processes, NDJSON over WS, async — duplicate or out-of-order events corrupt trajectories and Honcho's theory-of-mind.

**Mitigation:** monotonic `event_id` (ULID), idempotent `record_event`, **single-writer rule** (Hermes is the only writer to the canonical store; everything else proposes). No CRDT, no merge logic to debug.

### 3. Skill manifest fragmentation

If `agentskills.io` evolves while ClawHub adds proprietary fields, the dual-target lint becomes a maintenance tax that kills skill velocity.

**Mitigation:** claw-hermes upstreams the `runtimes:` block to `agentskills.io` in v0.3, treats ClawHub extensions as advisory not required, and refuses to publish a skill that uses ClawHub-only fields without an explicit override flag.

## Why not alternatives

| Alternative | Why we rejected it |
|---|---|
| Fork OpenClaw + bolt Hermes in | Fork = perpetual merge debt against a 365k-star moving target |
| Fork Hermes + add 24-channel adapters | Same problem, smaller surface |
| Pure CRDT for memory | Forks the dataset Hermes' RL depends on; merge logic = bugs forever |
| Port Hermes to TypeScript | 9 months of wasted work; loses Python ML ecosystem (Honcho, FTS5 tooling) |
| Port OpenClaw to Python | Loses the entire ClawHub skill base + 365k-star community |
| Two completely separate runtimes (status quo) | What HermesClaw tried — proven insufficient (WeChat-only, 239 stars) |

The bridge approach is the only one where **the user keeps their existing skills, channels, and memory while gaining the union's strengths.**

## Reading list

- Hermes Agent: https://github.com/NousResearch/hermes-agent — see `docs/developer-guide/architecture` and `environments/` (Atropos RL)
- OpenClaw: https://github.com/openclaw/openclaw — see `docs/concepts/architecture` and `docs/concepts/session`
- agentskills.io — open standard for portable skill manifests
- Honcho: https://github.com/plastic-labs/honcho — dialectic user modelling
- MCP: https://modelcontextprotocol.io — Anthropic's open agent-tool protocol
