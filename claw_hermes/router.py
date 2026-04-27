"""Pure routing logic: GitHub event → channel list, with urgency hints.

Kept as pure functions so they're trivially unit-testable without any external runtime.
"""
from __future__ import annotations

from dataclasses import dataclass

from claw_hermes.config import Config, RoutingRule

KNOWN_EVENTS = {
    "pr_opened",
    "pr_review_requested",
    "pr_merged",
    "pr_closed",
    "ci_failed",
    "ci_passed",
    "release_published",
    "issue_opened",
    "issue_closed",
    "daily_digest",
}

URGENCY_ORDER = {"urgent": 0, "normal": 1, "digest": 2}


@dataclass(frozen=True)
class RouteDecision:
    event: str
    channels: tuple[str, ...]
    urgency: str
    explanation: str

    def is_urgent(self) -> bool:
        return self.urgency == "urgent"


def decide(cfg: Config, event: str) -> RouteDecision:
    """Decide where a GitHub event should be delivered."""
    rule: RoutingRule = cfg.route_for(event)
    if not rule.channels:
        return RouteDecision(
            event=event,
            channels=tuple(cfg.default_channels),
            urgency=rule.urgency,
            explanation=f"no rule matched '{event}'; using default_channels",
        )
    return RouteDecision(
        event=event,
        channels=tuple(rule.channels),
        urgency=rule.urgency,
        explanation=f"matched rule '{rule.event}' urgency={rule.urgency}",
    )


def is_known_event(event: str) -> bool:
    return event in KNOWN_EVENTS


def sort_by_urgency(decisions: list[RouteDecision]) -> list[RouteDecision]:
    return sorted(decisions, key=lambda d: URGENCY_ORDER.get(d.urgency, 99))
