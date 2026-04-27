# Changelog

All notable changes to `claw-hermes` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [PEP 440](https://peps.python.org/pep-0440/) (`a` = alpha / preview).

---

## [0.2.0a1] — 2026-04-27 — Preview 1

The first three v0.2 features land as a prerelease. Wedge feature is usable today; federation pieces are scaffolds the v0.3 work will swap.

### Added — wedge

- **`slop-classify` command** — classifies a GitHub PR as `human` / `ai-slop` / `ai-assisted-legit` with a confidence score and named signals.
- **Heuristic detector** (no LLM required) — fires `ai_phrase_present`, `emoji_heavy_body`, `suspiciously_round_size`, `mass_rename_diff`, `hallucinated_import`, `no_tests_on_large_pr`, `templated_phrasing` with weighted scoring.
- **Hermes integration path** — calls `hermes --non-interactive` with a 3-line `LABEL/CONFIDENCE/REASONING` template; falls back to heuristic on any parse failure or non-zero exit.
- **Cross-repo signature store** — SQLite at `~/.claw-hermes/signatures.db`, recall by repo or author, stats summary. Foundation for the v0.3 cross-repo learning loop.

### Added — cross-runtime skills

- **`agentskills.io` v1.0 manifest schema with `runtimes:` extension** — declare `hermes` / `openclaw` / `both` entrypoints + capability hints in a single skill manifest.
- **`skill lint`** — 23 lint codes (`name.format`, `runtimes.empty`, `body.too_short`, `license.unknown`, etc.); supports `--json`, `--strict`. Exit codes 0/1/2 = clean/warning/error.
- **`skill new`** — scaffolder for `--runtime hermes|openclaw|both`; auto-runs the linter on the result; refuses to overwrite.
- **`skill list`** — discovers `*/SKILL.md` recursively, prints one-line summary per skill.
- **Documentation** — [`docs/manifest.md`](docs/manifest.md) covering the schema and every lint code; [`examples/skills/hello-world/`](examples/skills/hello-world/) as the minimal valid `runtimes: both` skill.

### Added — federation foundation (preview)

Conformant to [`ARCHITECTURE.md`](ARCHITECTURE.md) sections 1 + 3. v0.3 will swap the SQLite broker for a direct wrapper over Hermes' canonical FTS5 + Honcho store.

- **Unified `Event` type** (`claw_hermes/event.py`) — frozen dataclass; stdlib-only ULID `event_id` (Crockford-base32, monotonic within the same ms, threading-safe); NDJSON `to_json` / `from_json`; `KNOWN_KINDS` covering `message.inbound`, `message.outbound`, `github.pr.*`, `github.ci.*`, `github.issue.opened`, `system.heartbeat`.
- **`MemoryBroker` Protocol + `SqliteMemoryBroker`** (`claw_hermes/memory.py`) — single-writer SQLite + FTS5 over `payload.text`; idempotent on `event_id`; default DB at `~/.claw-hermes/memory.db`; `recall(query, kind, session_id, limit)`, `recent`, `count`, `close`.
- **Async event bus** (`claw_hermes/bus.py`) — `websockets`-based server + client; NDJSON wire format; `system.heartbeat` every 30s; malformed frames logged via `logging` and dropped.
- **CLI** — `claw-hermes memory show`, `memory record-test`, `bus serve`, `bus emit`.

### Project-wide

- **README.md** — repositioned with the "Letta with hands and ears" thesis; verified community numbers (OpenClaw 365k★ / 174k Discord, Hermes 119k★).
- **ROADMAP.md** — v0.2 → v1.0 trajectory with the wedge → expansion → consumer path.
- **ARCHITECTURE.md** — federation design (Hermes-as-canonical-store, `agentskills.io runtimes:` extension, dual MCP positioning, single-writer rule).
- **CI** — GitHub Actions workflow runs lint + pytest on Python 3.10/3.11/3.12.
- **Tests** — 120 mocked / pure-function tests, all green; no real network beyond loopback; no real `gh` calls in tests.

### Fixed

- `Config.route_for` — synthetic fallback rule no longer pre-fills `default_channels`, so `router.decide` correctly classifies unknown events as "no rule matched" rather than "matched rule" (silent miscategorisation that would have produced wrong observability data).

### Honest scope

Preview status. Real end-to-end Telegram/iMessage delivery still requires a configured OpenClaw daemon — operator-tested only, not maintainer-verified for this prerelease. The federation event bus is loopback-only; v0.4 adds auth/TLS/replay protection. The `MemoryBroker` does not yet wrap Hermes' canonical store — that swap is the v0.3 deliverable. Don't `pip install` expecting the full vision today; install if you're a maintainer who wants the GitHub piece, or a contributor who wants to help build the federation layer.

### Next

See [`ROADMAP.md`](ROADMAP.md). v0.3 collapses `SqliteMemoryBroker` into a Hermes-canonical wrapper, adds the user-identity graph (so iMessage events and Slack events from the same human collapse onto one session graph), and wires the slop classifier's signature store into the per-contributor Honcho model.

---

## [0.1.0] — 2026-04-27 — Initial release

- Click CLI scaffold (`claw-hermes` command)
- Real `gh` integration (`pr-fetch`, `pr-review`)
- Routing config (YAML) with urgency tiers
- Hermes integration with deterministic-skeleton fallback
- OpenClaw HTTP gateway client with dry-run mode
- Claude Code skill at `skill/SKILL.md`
- 15 mocked / pure-function tests
- MIT license, public repo

[0.2.0a1]: https://github.com/bertbertov/claw-hermes/releases/tag/v0.2.0a1
[0.1.0]: https://github.com/bertbertov/claw-hermes/releases/tag/v0.1.0
