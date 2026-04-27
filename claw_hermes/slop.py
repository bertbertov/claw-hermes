"""AI-slop PR classifier.

Two paths produce a verdict:
  1. Hermes installed → subprocess to it with `slop_template`, parse a 3-line response.
  2. No Hermes (or it errored) → deterministic heuristics over PR body + diff.

Heuristics are intentionally conservative: each fired signal is recorded in
`SlopVerdict.signals` so a downstream `SignatureStore` can learn which signals
correlate with merged-vs-rejected outcomes across repos.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal

from claw_hermes.config import HermesConfig
from claw_hermes.github import PullRequest

SlopLabel = Literal["human", "ai-slop", "ai-assisted-legit"]

_VALID_LABELS: tuple[SlopLabel, ...] = ("human", "ai-slop", "ai-assisted-legit")

_AI_PHRASES = (
    "as an ai",
    "as a language model",
    "i cannot",
    "i'm an ai",
    "i am an ai",
    "generated with",
    "co-authored-by: claude",
    "co-authored-by: chatgpt",
    "co-authored-by: copilot",
    "this pr was generated",
    "🤖 generated",
    "made with chatgpt",
    "made with claude",
    "powered by gpt",
)

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF]"
)

_HALLUCINATED_IMPORTS_RE = re.compile(
    r"\b(?:import|from)\s+("
    r"requests_async"
    r"|json_helper"
    r"|easy_http"
    r"|pyutils_extra"
    r"|stdlib_extras"
    r"|os_helpers"
    r"|sys_extras"
    r"|fastjson"
    r")\b"
)


@dataclass(frozen=True)
class SlopVerdict:
    label: SlopLabel
    confidence: float
    signals: tuple[str, ...]
    reasoning: str
    used_hermes: bool


def classify(cfg: HermesConfig, pr: PullRequest, diff: str) -> SlopVerdict:
    """Classify a PR. Tries Hermes first; falls back to heuristics on any failure."""
    hermes_verdict = _try_hermes(cfg, pr, diff)
    if hermes_verdict is not None:
        return hermes_verdict
    return _heuristic_classify(pr, diff)


def _try_hermes(cfg: HermesConfig, pr: PullRequest, diff: str) -> SlopVerdict | None:
    if not cfg.enabled:
        return None
    if not shutil.which(cfg.binary):
        return None
    prompt = cfg.slop_template.format(
        title=pr.title,
        author=pr.author,
        changed_files=pr.changed_files,
        body=pr.body or "(empty)",
        diff=diff,
    )
    cmd = [cfg.binary, "--non-interactive", "--prompt", prompt]
    if cfg.model:
        cmd.extend(["--model", cfg.model])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    parsed = _parse_hermes_output(result.stdout)
    if parsed is None:
        return None
    label, confidence, reasoning = parsed
    return SlopVerdict(
        label=label,
        confidence=confidence,
        signals=("hermes",),
        reasoning=reasoning,
        used_hermes=True,
    )


def _parse_hermes_output(text: str) -> tuple[SlopLabel, float, str] | None:
    label: SlopLabel | None = None
    confidence: float | None = None
    reasoning = ""
    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("LABEL:"):
            value = stripped.split(":", 1)[1].strip().lower()
            if value in _VALID_LABELS:
                label = value  # type: ignore[assignment]
        elif upper.startswith("CONFIDENCE:"):
            value = stripped.split(":", 1)[1].strip()
            try:
                confidence = max(0.0, min(1.0, float(value)))
            except ValueError:
                confidence = None
        elif upper.startswith("REASONING:"):
            reasoning = stripped.split(":", 1)[1].strip()
    if label is None or confidence is None:
        return None
    return label, confidence, reasoning or "(no reasoning provided)"


def _heuristic_classify(pr: PullRequest, diff: str) -> SlopVerdict:
    signals: list[str] = []
    body = pr.body or ""

    if _emoji_density(body) > 0.05 and len(body) >= 40:
        signals.append("emoji_heavy_body")

    body_lower = body.lower()
    title_lower = pr.title.lower()
    for phrase in _AI_PHRASES:
        if phrase in body_lower or phrase in title_lower:
            signals.append("ai_phrase_present")
            break

    total_lines = pr.additions + pr.deletions
    if total_lines >= 100 and total_lines % 100 == 0:
        signals.append("suspiciously_round_size")

    if pr.changed_files >= 10 and pr.additions == pr.deletions and pr.additions > 0:
        signals.append("mass_rename_diff")

    if _HALLUCINATED_IMPORTS_RE.search(diff):
        signals.append("hallucinated_import")

    if total_lines > 100 and not _diff_touches_tests(diff):
        signals.append("no_tests_on_large_pr")

    if _looks_like_template_phrasing(body):
        signals.append("templated_phrasing")

    score = _score_from_signals(signals)
    label, reasoning = _label_and_reason(pr, total_lines, signals, score)
    confidence = _confidence_from_signals(score, label)

    return SlopVerdict(
        label=label,
        confidence=confidence,
        signals=tuple(signals),
        reasoning=reasoning,
        used_hermes=False,
    )


def _emoji_density(text: str) -> float:
    if not text:
        return 0.0
    matches = _EMOJI_RE.findall(text)
    return len(matches) / max(len(text), 1)


def _diff_touches_tests(diff: str) -> bool:
    for line in diff.splitlines():
        if not line.startswith(("+++ ", "--- ", "diff --git ")):
            continue
        lower = line.lower()
        if "/test" in lower or "test_" in lower or "_test." in lower or "/spec" in lower:
            return True
    return False


def _looks_like_template_phrasing(body: str) -> bool:
    markers = (
        "## summary",
        "## changes",
        "## test plan",
        "## what",
        "## why",
        "- [x]",
        "- [ ]",
    )
    hits = sum(1 for m in markers if m in body.lower())
    return hits >= 4


def _score_from_signals(signals: list[str]) -> int:
    weights = {
        "ai_phrase_present": 3,
        "hallucinated_import": 3,
        "mass_rename_diff": 2,
        "emoji_heavy_body": 2,
        "suspiciously_round_size": 1,
        "no_tests_on_large_pr": 1,
        "templated_phrasing": 1,
    }
    return sum(weights.get(s, 1) for s in signals)


def _label_and_reason(
    pr: PullRequest, total_lines: int, signals: list[str], score: int
) -> tuple[SlopLabel, str]:
    if score >= 4:
        return "ai-slop", f"strong slop signals: {', '.join(signals)}"
    if score >= 2:
        if "templated_phrasing" in signals and total_lines > 20:
            return "ai-assisted-legit", f"AI-assisted but plausibly legit: {', '.join(signals)}"
        return "ai-slop", f"multiple slop signals: {', '.join(signals)}"
    if score == 1:
        return "ai-assisted-legit", f"one weak signal fired: {', '.join(signals)}"
    if total_lines <= 10 and pr.changed_files <= 2:
        return "human", "small typo-fix-shaped PR with no slop signals"
    return "human", "no slop signals detected"


def _confidence_from_signals(score: int, label: SlopLabel) -> float:
    if label == "human":
        return 0.7 if score == 0 else 0.55
    if label == "ai-assisted-legit":
        return 0.55
    return min(0.95, 0.6 + 0.1 * score)
