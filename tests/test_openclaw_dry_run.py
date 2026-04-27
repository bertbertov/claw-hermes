"""OpenClaw delivery tests — uses dry_run so no real HTTP traffic ever leaves the box."""
from __future__ import annotations

from claw_hermes import openclaw
from claw_hermes.config import OpenClawConfig


def test_dry_run_returns_intended_targets_without_network():
    cfg = OpenClawConfig(gateway_url="http://example.invalid:1", enabled=True)
    result = openclaw.deliver(cfg, ["telegram", "discord"], "hi", dry_run=True)
    assert result.dry_run is True
    assert result.delivered_to == ("telegram", "discord")
    assert result.failed == ()


def test_disabled_config_short_circuits_to_dry_run():
    cfg = OpenClawConfig(enabled=False)
    result = openclaw.deliver(cfg, ["slack"], "hi", dry_run=False)
    assert result.dry_run is True
    assert result.delivered_to == ("slack",)


def test_probe_against_unreachable_url_reports_error():
    cfg = OpenClawConfig(gateway_url="http://127.0.0.1:1", timeout_seconds=0.5)
    avail = openclaw.probe(cfg)
    assert avail.reachable is False
    assert avail.error is not None
