"""Hermes Agent integration — the learning-loop side of the marriage.

When `hermes` is installed, claw-hermes uses it for:
  - PR review generation (calls `hermes` non-interactively with a prompt template)
  - Future: FTS5 session search of past similar PRs, Honcho contributor models, skill autogeneration

When `hermes` is NOT installed, every method returns a `HermesUnavailable` stub
without raising — the caller decides whether to degrade gracefully or surface an error.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from claw_hermes.config import HermesConfig
from claw_hermes.github import PullRequest


@dataclass(frozen=True)
class HermesAvailability:
    installed: bool
    binary_path: str | None
    version: str | None
    error: str | None = None


@dataclass(frozen=True)
class ReviewResult:
    summary: str
    used_hermes: bool
    raw_output: str | None = None
    error: str | None = None


def probe(cfg: HermesConfig) -> HermesAvailability:
    """Check whether Hermes is installed and callable. No state changes."""
    path = shutil.which(cfg.binary)
    if not path:
        return HermesAvailability(installed=False, binary_path=None, version=None,
                                   error=f"`{cfg.binary}` not found in PATH")
    try:
        out = subprocess.run([cfg.binary, "--version"], capture_output=True,
                             text=True, timeout=5, check=False)
        version = (out.stdout or out.stderr).strip().splitlines()[0] if out.returncode == 0 else None
        return HermesAvailability(installed=True, binary_path=path, version=version)
    except Exception as e:  # noqa: BLE001 — diagnostic surface
        return HermesAvailability(installed=True, binary_path=path, version=None, error=str(e))


def review_pr(cfg: HermesConfig, pr: PullRequest, diff: str) -> ReviewResult:
    """Ask Hermes to review a PR. Falls back to a deterministic skeleton if Hermes is missing.

    Side effects: when Hermes is installed, this DOES call out to the configured LLM
    (creating a session). When Hermes is not installed, this is pure.
    """
    avail = probe(cfg)
    prompt = cfg.review_template.format(
        title=pr.title, author=pr.author, changed_files=pr.changed_files, diff=diff,
    )
    if not avail.installed or not cfg.enabled:
        return _fallback_review(pr, diff, reason=avail.error or "hermes disabled in config")

    cmd = [cfg.binary, "--non-interactive", "--prompt", prompt]
    if cfg.model:
        cmd.extend(["--model", cfg.model])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        return ReviewResult(summary="(hermes timed out at 120s)", used_hermes=True,
                            error="timeout")
    if result.returncode != 0:
        return ReviewResult(
            summary=f"(hermes exited {result.returncode})",
            used_hermes=True,
            raw_output=result.stdout,
            error=result.stderr.strip(),
        )
    return ReviewResult(summary=result.stdout.strip(), used_hermes=True,
                        raw_output=result.stdout)


def _fallback_review(pr: PullRequest, diff: str, reason: str) -> ReviewResult:
    """Pure-Python deterministic skeleton when Hermes isn't available.

    Useful for CI smoke tests and for users who want to see the routing layer work
    before they install Hermes.
    """
    size_label = "tiny" if pr.changed_files <= 2 else "medium" if pr.changed_files <= 10 else "large"
    additions_label = "minor" if pr.additions < 50 else "significant" if pr.additions < 500 else "huge"
    summary = (
        f"## PR #{pr.number} — {pr.title}\n"
        f"**Author:** @{pr.author}  •  **Size:** {size_label} ({pr.changed_files} files, "
        f"+{pr.additions}/-{pr.deletions})  •  **Change scale:** {additions_label}\n\n"
        f"_Hermes unavailable ({reason}); this is a deterministic skeleton, not an AI review._\n\n"
        f"- Diff length probed: {len(diff)} bytes\n"
        f"- {pr.url}\n"
    )
    return ReviewResult(summary=summary, used_hermes=False, error=reason)
