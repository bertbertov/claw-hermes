"""OpenClaw Gateway integration — the multi-channel delivery side of the marriage.

OpenClaw exposes a local HTTP gateway (default :18789) that receives messages and
fans them out to ~24 channel types (Telegram, WhatsApp, Discord, Slack, iMessage,
WeChat, Matrix, etc.).

This module never assumes an OpenClaw daemon is running. `probe()` is a single
non-mutating health check, and `deliver()` only POSTs when explicitly invoked.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from claw_hermes.config import OpenClawConfig


@dataclass(frozen=True)
class GatewayAvailability:
    reachable: bool
    url: str
    status_code: int | None
    error: str | None = None


@dataclass(frozen=True)
class DeliveryResult:
    delivered_to: tuple[str, ...]
    failed: tuple[str, ...]
    dry_run: bool
    raw_responses: dict[str, int] | None = None


def probe(cfg: OpenClawConfig, *, path: str = "/health") -> GatewayAvailability:
    """Issue a non-mutating GET to the gateway. No side effects."""
    url = cfg.gateway_url.rstrip("/") + path
    try:
        with httpx.Client(timeout=cfg.timeout_seconds) as client:
            resp = client.get(url)
        return GatewayAvailability(
            reachable=resp.status_code < 500,
            url=url,
            status_code=resp.status_code,
        )
    except httpx.HTTPError as e:
        return GatewayAvailability(reachable=False, url=url, status_code=None, error=str(e))


def deliver(
    cfg: OpenClawConfig,
    channels: list[str],
    message: str,
    *,
    title: str | None = None,
    dry_run: bool = False,
) -> DeliveryResult:
    """Post a message to one or more channels via the OpenClaw gateway.

    Set `dry_run=True` to skip the HTTP call entirely — useful in CI or when
    the gateway isn't running. Returns the channels that would-have-been targeted.
    """
    if dry_run or not cfg.enabled:
        return DeliveryResult(
            delivered_to=tuple(channels),
            failed=(),
            dry_run=True,
        )

    delivered: list[str] = []
    failed: list[str] = []
    raw: dict[str, int] = {}
    url = cfg.gateway_url.rstrip("/") + "/v1/message"
    payload_base = {"text": message}
    if title:
        payload_base["title"] = title

    with httpx.Client(timeout=cfg.timeout_seconds) as client:
        for ch in channels:
            try:
                resp = client.post(url, json={**payload_base, "channel": ch})
                raw[ch] = resp.status_code
                if resp.is_success:
                    delivered.append(ch)
                else:
                    failed.append(ch)
            except httpx.HTTPError:
                failed.append(ch)
                raw[ch] = -1

    return DeliveryResult(
        delivered_to=tuple(delivered),
        failed=tuple(failed),
        dry_run=False,
        raw_responses=raw,
    )
