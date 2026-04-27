"""SignatureStore tests — uses tmp_path so we never touch ~/.claw-hermes/."""
from __future__ import annotations

from pathlib import Path

from claw_hermes.signatures import SignatureStore
from claw_hermes.slop import SlopVerdict


def _verdict(label: str = "ai-slop", signals: tuple[str, ...] = ("ai_phrase_present",)) -> SlopVerdict:
    return SlopVerdict(
        label=label,  # type: ignore[arg-type]
        confidence=0.8,
        signals=signals,
        reasoning="test verdict",
        used_hermes=False,
    )


def test_record_and_recall_roundtrip(tmp_path: Path):
    store = SignatureStore(db_path=tmp_path / "sigs.db")
    rid = store.record(_verdict(), repo="owner/repo", pr_number=42, author="alice")
    assert rid > 0
    rows = store.recall()
    assert len(rows) == 1
    row = rows[0]
    assert row.repo == "owner/repo"
    assert row.pr_number == 42
    assert row.author == "alice"
    assert row.label == "ai-slop"
    assert row.signals == ("ai_phrase_present",)
    assert row.source == "manual"


def test_recall_filters_by_repo(tmp_path: Path):
    store = SignatureStore(db_path=tmp_path / "sigs.db")
    store.record(_verdict(), repo="a/x", pr_number=1, author="alice")
    store.record(_verdict(), repo="b/y", pr_number=1, author="bob")
    rows = store.recall(repo="a/x")
    assert len(rows) == 1
    assert rows[0].repo == "a/x"


def test_recall_filters_by_author(tmp_path: Path):
    store = SignatureStore(db_path=tmp_path / "sigs.db")
    store.record(_verdict(), repo="a/x", pr_number=1, author="alice")
    store.record(_verdict(), repo="a/x", pr_number=2, author="bob")
    store.record(_verdict(label="human", signals=()), repo="a/x", pr_number=3, author="alice")
    rows = store.recall(author="alice")
    assert {r.pr_number for r in rows} == {1, 3}
    assert all(r.author == "alice" for r in rows)


def test_recall_limits_results(tmp_path: Path):
    store = SignatureStore(db_path=tmp_path / "sigs.db")
    for i in range(10):
        store.record(_verdict(), repo="a/x", pr_number=i, author="alice")
    rows = store.recall(limit=3)
    assert len(rows) == 3


def test_stats_counts_labels_and_signals(tmp_path: Path):
    store = SignatureStore(db_path=tmp_path / "sigs.db")
    store.record(_verdict(label="ai-slop", signals=("ai_phrase_present",)),
                 repo="a/x", pr_number=1, author="alice")
    store.record(_verdict(label="ai-slop", signals=("emoji_heavy_body", "ai_phrase_present")),
                 repo="a/x", pr_number=2, author="alice")
    store.record(_verdict(label="human", signals=()),
                 repo="a/x", pr_number=3, author="bob")

    stats = store.stats()
    assert stats["total"] == 3
    assert stats["label:ai-slop"] == 2
    assert stats["label:human"] == 1
    assert stats["signal:ai_phrase_present"] == 2
    assert stats["signal:emoji_heavy_body"] == 1


def test_source_tag_persists(tmp_path: Path):
    store = SignatureStore(db_path=tmp_path / "sigs.db")
    store.record(_verdict(), repo="a/x", pr_number=1, author="alice", source="auto")
    rows = store.recall()
    assert rows[0].source == "auto"
