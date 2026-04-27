"""Hermes fallback tests — exercises the deterministic skeleton when hermes binary is absent."""
from __future__ import annotations

from unittest.mock import patch

from claw_hermes import hermes
from claw_hermes.config import HermesConfig
from claw_hermes.github import PullRequest


def _fake_pr() -> PullRequest:
    return PullRequest(
        repo="owner/repo", number=42, title="Add new feature",
        author="alice", state="OPEN", is_draft=False,
        additions=120, deletions=5, changed_files=4,
        url="https://github.com/owner/repo/pull/42", body="",
    )


def test_probe_reports_not_installed_when_binary_missing():
    cfg = HermesConfig(binary="definitely-not-on-path-zzz")
    avail = hermes.probe(cfg)
    assert avail.installed is False
    assert avail.binary_path is None
    assert "not found" in (avail.error or "")


def test_review_pr_falls_back_when_hermes_missing():
    cfg = HermesConfig(binary="definitely-not-on-path-zzz")
    result = hermes.review_pr(cfg, _fake_pr(), "diff content")
    assert result.used_hermes is False
    assert "PR #42" in result.summary
    assert "@alice" in result.summary
    assert "deterministic skeleton" in result.summary


def test_review_pr_calls_hermes_when_probe_succeeds(tmp_path):
    """When hermes appears on PATH, review_pr must subprocess to it.

    We mock both the PATH probe AND the subprocess call so no real binary is invoked.
    """
    cfg = HermesConfig(binary="hermes-fake")
    fake_path = str(tmp_path / "hermes-fake")
    with patch("shutil.which", return_value=fake_path), \
         patch("subprocess.run") as mock_run:
        # First call is probe (--version), second is the review.
        mock_run.side_effect = [
            type("R", (), {"returncode": 0, "stdout": "hermes 0.10.0\n", "stderr": ""})(),
            type("R", (), {"returncode": 0, "stdout": "Looks fine.", "stderr": ""})(),
        ]
        result = hermes.review_pr(cfg, _fake_pr(), "diff content")
    assert result.used_hermes is True
    assert "Looks fine." in result.summary
