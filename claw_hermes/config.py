"""Config loader for claw-hermes routing rules and runtime endpoints."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(os.path.expanduser("~/.claw-hermes/config.yaml"))


@dataclass
class HermesConfig:
    binary: str = "hermes"
    enabled: bool = True
    model: str | None = None
    review_template: str = (
        "Review this GitHub PR. Be terse. Flag risk, missing tests, breaking changes.\n\n"
        "Title: {title}\nAuthor: {author}\nFiles changed: {changed_files}\n\n"
        "Diff (truncated to 8KB):\n{diff}\n"
    )
    slop_template: str = (
        "Classify this GitHub PR as one of: human, ai-slop, ai-assisted-legit.\n"
        "Reply on three lines, exactly:\n"
        "LABEL: <human|ai-slop|ai-assisted-legit>\n"
        "CONFIDENCE: <0.0-1.0>\n"
        "REASONING: <one short sentence>\n\n"
        "Title: {title}\nAuthor: {author}\nFiles changed: {changed_files}\n"
        "Body:\n{body}\n\n"
        "Diff (truncated to 8KB):\n{diff}\n"
    )


@dataclass
class OpenClawConfig:
    gateway_url: str = "http://localhost:18789"
    enabled: bool = True
    timeout_seconds: float = 5.0


@dataclass
class RoutingRule:
    """Where a GitHub event type gets delivered, and how urgently."""
    event: str
    channels: list[str] = field(default_factory=list)
    urgency: str = "normal"  # urgent | normal | digest


@dataclass
class Config:
    hermes: HermesConfig = field(default_factory=HermesConfig)
    openclaw: OpenClawConfig = field(default_factory=OpenClawConfig)
    routes: list[RoutingRule] = field(default_factory=list)
    default_channels: list[str] = field(default_factory=lambda: ["cli"])

    @classmethod
    def default(cls) -> "Config":
        return cls(
            routes=[
                RoutingRule(event="ci_failed", channels=["imessage", "telegram"], urgency="urgent"),
                RoutingRule(event="pr_review_requested", channels=["telegram", "slack"], urgency="normal"),
                RoutingRule(event="pr_opened", channels=["slack"], urgency="normal"),
                RoutingRule(event="pr_merged", channels=["discord"], urgency="normal"),
                RoutingRule(event="release_published", channels=["discord", "slack"], urgency="normal"),
                RoutingRule(event="daily_digest", channels=["email", "telegram"], urgency="digest"),
                RoutingRule(event="issue_opened", channels=["slack"], urgency="normal"),
            ],
            default_channels=["cli"],
        )

    def route_for(self, event: str) -> RoutingRule:
        for r in self.routes:
            if r.event == event:
                return r
        return RoutingRule(event=event)  # channels=[] => router.decide applies default_channels

    def to_dict(self) -> dict[str, Any]:
        return {
            "hermes": {
                "binary": self.hermes.binary,
                "enabled": self.hermes.enabled,
                "model": self.hermes.model,
                "review_template": self.hermes.review_template,
                "slop_template": self.hermes.slop_template,
            },
            "openclaw": {
                "gateway_url": self.openclaw.gateway_url,
                "enabled": self.openclaw.enabled,
                "timeout_seconds": self.openclaw.timeout_seconds,
            },
            "default_channels": self.default_channels,
            "routes": [
                {"event": r.event, "channels": r.channels, "urgency": r.urgency}
                for r in self.routes
            ],
        }


def load(path: Path | str | None = None) -> Config:
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        return Config.default()
    raw = yaml.safe_load(p.read_text()) or {}
    cfg = Config.default()
    if "hermes" in raw:
        h = raw["hermes"]
        cfg.hermes = HermesConfig(
            binary=h.get("binary", cfg.hermes.binary),
            enabled=h.get("enabled", cfg.hermes.enabled),
            model=h.get("model", cfg.hermes.model),
            review_template=h.get("review_template", cfg.hermes.review_template),
            slop_template=h.get("slop_template", cfg.hermes.slop_template),
        )
    if "openclaw" in raw:
        o = raw["openclaw"]
        cfg.openclaw = OpenClawConfig(
            gateway_url=o.get("gateway_url", cfg.openclaw.gateway_url),
            enabled=o.get("enabled", cfg.openclaw.enabled),
            timeout_seconds=o.get("timeout_seconds", cfg.openclaw.timeout_seconds),
        )
    if "default_channels" in raw:
        cfg.default_channels = list(raw["default_channels"])
    if "routes" in raw:
        cfg.routes = [
            RoutingRule(
                event=r["event"],
                channels=list(r.get("channels", [])),
                urgency=r.get("urgency", "normal"),
            )
            for r in raw["routes"]
        ]
    return cfg


def save(cfg: Config, path: Path | str | None = None) -> Path:
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(cfg.to_dict(), sort_keys=False))
    return p
