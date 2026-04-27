"""Thin wrapper around the `gh` CLI.

We intentionally subprocess to `gh` rather than using PyGithub:
  - reuses the user's existing auth (no extra token plumbing)
  - works with both github.com and ghes hosts the user has configured
  - matches OpenClaw and Hermes which already lean on `gh` for repo ops
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass


class GhNotFoundError(RuntimeError):
    pass


class GhCallError(RuntimeError):
    pass


@dataclass(frozen=True)
class PullRequest:
    repo: str
    number: int
    title: str
    author: str
    state: str
    is_draft: bool
    additions: int
    deletions: int
    changed_files: int
    url: str
    body: str

    @classmethod
    def from_gh_json(cls, repo: str, data: dict) -> "PullRequest":
        return cls(
            repo=repo,
            number=int(data.get("number", 0)),
            title=data.get("title", ""),
            author=(data.get("author") or {}).get("login", "unknown"),
            state=data.get("state", ""),
            is_draft=bool(data.get("isDraft", False)),
            additions=int(data.get("additions", 0)),
            deletions=int(data.get("deletions", 0)),
            changed_files=int(data.get("changedFiles", 0)),
            url=data.get("url", ""),
            body=data.get("body", "") or "",
        )


def _ensure_gh() -> str:
    path = shutil.which("gh")
    if not path:
        raise GhNotFoundError(
            "`gh` CLI not found. Install: https://cli.github.com/  Then `gh auth login`."
        )
    return path


def _run(args: list[str], timeout: float = 30.0) -> str:
    _ensure_gh()
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise GhCallError(f"gh command timed out after {timeout}s: {' '.join(args)}") from e
    if result.returncode != 0:
        raise GhCallError(
            f"gh exited {result.returncode}: {' '.join(args)}\nstderr: {result.stderr.strip()}"
        )
    return result.stdout


def fetch_pr(repo: str, number: int) -> PullRequest:
    """Fetch a single pull request's metadata."""
    fields = "number,title,author,state,isDraft,additions,deletions,changedFiles,url,body"
    out = _run(["pr", "view", str(number), "--repo", repo, "--json", fields])
    return PullRequest.from_gh_json(repo, json.loads(out))


def fetch_pr_diff(repo: str, number: int, max_bytes: int = 8192) -> str:
    """Fetch the unified diff of a PR, truncated to max_bytes for prompt-size hygiene."""
    out = _run(["pr", "diff", str(number), "--repo", repo])
    if len(out) > max_bytes:
        return out[:max_bytes] + f"\n\n[... truncated, full diff was {len(out)} bytes ...]"
    return out


def list_open_prs(repo: str, limit: int = 20) -> list[dict]:
    """List open PRs with minimal metadata for digest generation."""
    fields = "number,title,author,createdAt,isDraft,reviewDecision,url"
    out = _run(["pr", "list", "--repo", repo, "--state", "open",
                "--limit", str(limit), "--json", fields])
    return json.loads(out)


def whoami() -> str | None:
    """Return the authenticated GitHub login, or None if not authed."""
    try:
        out = _run(["api", "user", "--jq", ".login"])
        return out.strip() or None
    except (GhNotFoundError, GhCallError):
        return None
