"""Pure-function tests for the routing layer — no network, no subprocess."""
from __future__ import annotations

from claw_hermes import router
from claw_hermes.config import Config, RoutingRule


def test_decide_matches_known_event_and_returns_configured_channels():
    cfg = Config.default()
    decision = router.decide(cfg, "ci_failed")
    assert decision.event == "ci_failed"
    assert "imessage" in decision.channels
    assert "telegram" in decision.channels
    assert decision.urgency == "urgent"
    assert decision.is_urgent()


def test_decide_falls_back_to_default_channels_for_unknown_event():
    cfg = Config(default_channels=["cli", "email"])
    decision = router.decide(cfg, "totally_made_up_event")
    assert decision.channels == ("cli", "email")
    assert "no rule matched" in decision.explanation


def test_decide_uses_explicit_rule_over_defaults():
    cfg = Config(
        default_channels=["cli"],
        routes=[RoutingRule(event="custom", channels=["matrix"], urgency="digest")],
    )
    decision = router.decide(cfg, "custom")
    assert decision.channels == ("matrix",)
    assert decision.urgency == "digest"
    assert not decision.is_urgent()


def test_is_known_event_recognises_core_set():
    assert router.is_known_event("pr_opened")
    assert router.is_known_event("ci_failed")
    assert not router.is_known_event("definitely_not_an_event")


def test_sort_by_urgency_orders_urgent_first_then_normal_then_digest():
    cfg = Config.default()
    decisions = [
        router.decide(cfg, "daily_digest"),       # digest
        router.decide(cfg, "ci_failed"),          # urgent
        router.decide(cfg, "pr_opened"),          # normal
    ]
    sorted_d = router.sort_by_urgency(decisions)
    assert [d.urgency for d in sorted_d] == ["urgent", "normal", "digest"]
