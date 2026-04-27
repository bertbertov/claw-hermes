"""claw-hermes CLI — the user-facing surface that ties everything together."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from claw_hermes import __version__, config as config_mod, github, hermes, openclaw, router


@click.group()
@click.version_option(__version__, prog_name="claw-hermes")
@click.option("--config", "config_path", type=click.Path(dir_okay=False), default=None,
              help="Path to config.yaml (default: ~/.claw-hermes/config.yaml).")
@click.pass_context
def main(ctx: click.Context, config_path: str | None) -> None:
    """Marriage of OpenClaw + Hermes Agent for GitHub workflow orchestration."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["config"] = config_mod.load(config_path)


@main.command()
@click.option("--force", is_flag=True, help="Overwrite an existing config.")
@click.pass_context
def init(ctx: click.Context, force: bool) -> None:
    """Write a default routing config to ~/.claw-hermes/config.yaml."""
    target = Path(ctx.obj["config_path"]) if ctx.obj["config_path"] else config_mod.DEFAULT_CONFIG_PATH
    if target.exists() and not force:
        click.echo(f"Config already exists at {target}. Use --force to overwrite.", err=True)
        sys.exit(1)
    cfg = config_mod.Config.default()
    written = config_mod.save(cfg, target)
    click.echo(f"Wrote default config to {written}")
    click.echo(f"  routes: {len(cfg.routes)}  default_channels: {cfg.default_channels}")


@main.command()
@click.argument("event")
@click.pass_context
def route(ctx: click.Context, event: str) -> None:
    """Show which channels a GitHub event would route to."""
    decision = router.decide(ctx.obj["config"], event)
    if not router.is_known_event(event):
        click.echo(f"warning: '{event}' is not a known event type "
                   f"(known: {', '.join(sorted(router.KNOWN_EVENTS))})", err=True)
    click.echo(f"event:    {decision.event}")
    click.echo(f"channels: {', '.join(decision.channels)}")
    click.echo(f"urgency:  {decision.urgency}")
    click.echo(f"why:      {decision.explanation}")


@main.command("pr-fetch")
@click.argument("repo")
@click.argument("number", type=int)
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON instead of summary.")
def pr_fetch(repo: str, number: int, as_json: bool) -> None:
    """Fetch a pull request via `gh` (read-only). Format: owner/repo."""
    try:
        pr = github.fetch_pr(repo, number)
    except github.GhNotFoundError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(2)
    except github.GhCallError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(3)
    if as_json:
        click.echo(json.dumps(pr.__dict__, indent=2))
        return
    click.echo(f"#{pr.number} {pr.title}")
    click.echo(f"  author:  @{pr.author}")
    click.echo(f"  state:   {pr.state}{' (draft)' if pr.is_draft else ''}")
    click.echo(f"  changes: {pr.changed_files} files, +{pr.additions}/-{pr.deletions}")
    click.echo(f"  url:     {pr.url}")


@main.command("pr-review")
@click.argument("repo")
@click.argument("number", type=int)
@click.option("--deliver", is_flag=True,
              help="After review, route digest through OpenClaw (uses pr_review_requested rule).")
@click.option("--dry-run", is_flag=True,
              help="With --deliver, skip the actual HTTP POST to the gateway.")
@click.pass_context
def pr_review(ctx: click.Context, repo: str, number: int, deliver: bool, dry_run: bool) -> None:
    """Generate a PR review digest via Hermes (or skeleton fallback)."""
    cfg = ctx.obj["config"]
    pr = github.fetch_pr(repo, number)
    diff = github.fetch_pr_diff(repo, number)
    result = hermes.review_pr(cfg.hermes, pr, diff)
    click.echo(result.summary)
    if result.error and not result.used_hermes:
        click.echo(f"\n(fallback used: {result.error})", err=True)
    if deliver:
        decision = router.decide(cfg, "pr_review_requested")
        delivery = openclaw.deliver(
            cfg.openclaw, list(decision.channels), result.summary,
            title=f"PR #{pr.number}: {pr.title}", dry_run=dry_run,
        )
        click.echo(f"\nrouted to: {', '.join(delivery.delivered_to)}"
                   + (" [dry-run]" if delivery.dry_run else ""))
        if delivery.failed:
            click.echo(f"failed:    {', '.join(delivery.failed)}", err=True)


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show what's wired up: config, hermes availability, OpenClaw reachability, gh auth."""
    cfg = ctx.obj["config"]
    click.echo(f"claw-hermes {__version__}")
    click.echo(f"config:   {ctx.obj['config_path'] or config_mod.DEFAULT_CONFIG_PATH}")
    click.echo(f"routes:   {len(cfg.routes)} configured")

    gh_user = github.whoami()
    click.echo(f"\ngh:       {'authed as @' + gh_user if gh_user else 'NOT authenticated'}")

    h = hermes.probe(cfg.hermes)
    if h.installed:
        click.echo(f"hermes:   installed at {h.binary_path} ({h.version or '? version'})")
    else:
        click.echo(f"hermes:   not installed ({h.error})")

    o = openclaw.probe(cfg.openclaw)
    if o.reachable:
        click.echo(f"openclaw: gateway reachable at {o.url} (HTTP {o.status_code})")
    else:
        click.echo(f"openclaw: gateway NOT reachable ({o.error or 'no response'})")


@main.command("hermes-probe")
@click.pass_context
def hermes_probe(ctx: click.Context) -> None:
    """Read-only check that Hermes is callable. Does NOT start a session."""
    avail = hermes.probe(ctx.obj["config"].hermes)
    click.echo(json.dumps(avail.__dict__, indent=2))


@main.command("openclaw-probe")
@click.pass_context
def openclaw_probe(ctx: click.Context) -> None:
    """Read-only HTTP GET to the OpenClaw gateway health endpoint."""
    avail = openclaw.probe(ctx.obj["config"].openclaw)
    click.echo(json.dumps(avail.__dict__, indent=2))


if __name__ == "__main__":
    main()
