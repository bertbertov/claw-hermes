"""Config round-trip tests — write defaults, read them back, mutate, save, reload."""
from __future__ import annotations

from pathlib import Path

from claw_hermes import config as config_mod
from claw_hermes.config import Config, OpenClawConfig, RoutingRule


def test_default_config_has_sane_routes():
    cfg = Config.default()
    events = {r.event for r in cfg.routes}
    assert {"ci_failed", "pr_opened", "release_published", "daily_digest"}.issubset(events)


def test_save_then_load_roundtrip(tmp_path: Path):
    target = tmp_path / "config.yaml"
    cfg = Config.default()
    cfg.openclaw.gateway_url = "http://my-host:9999"
    cfg.routes.append(RoutingRule(event="custom_event", channels=["matrix"], urgency="urgent"))
    config_mod.save(cfg, target)
    assert target.exists()
    reloaded = config_mod.load(target)
    assert reloaded.openclaw.gateway_url == "http://my-host:9999"
    assert any(r.event == "custom_event" for r in reloaded.routes)


def test_load_nonexistent_returns_defaults(tmp_path: Path):
    cfg = config_mod.load(tmp_path / "nope.yaml")
    assert isinstance(cfg.openclaw, OpenClawConfig)
    assert len(cfg.routes) > 0


def test_route_for_returns_configured_or_synthetic_rule():
    cfg = Config.default()
    rule = cfg.route_for("ci_failed")
    assert rule.urgency == "urgent"
    synthetic = cfg.route_for("not_in_config")
    assert synthetic.event == "not_in_config"
    assert synthetic.channels == []
