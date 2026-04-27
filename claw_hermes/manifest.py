"""Skill manifest schema and linter for the agentskills.io v1.0 + ``runtimes:`` extension.

Manifests are Markdown files with YAML frontmatter delimited by ``---`` lines. The frontmatter
declares dual-runtime metadata (hermes / openclaw / both) and the body is the human-facing
skill description. ``lint`` returns a stable, code-keyed list of issues so callers can render
or filter without re-parsing free-text messages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

SUPPORTED_AGENTSKILLS_VERSIONS: frozenset[str] = frozenset({"1.0"})

KNOWN_RUNTIME_KEYS: frozenset[str] = frozenset({"hermes", "openclaw", "both"})

KNOWN_CAPABILITIES: frozenset[str] = frozenset({
    "github",
    "memory.recall",
    "memory.write",
    "channels.send",
    "channels.receive",
    "subprocess",
    "network",
    "filesystem.read",
    "filesystem.write",
})

KNOWN_LICENSES: frozenset[str] = frozenset({
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "GPL-2.0",
    "GPL-3.0",
    "LGPL-2.1",
    "LGPL-3.0",
    "MPL-2.0",
    "ISC",
    "Unlicense",
    "CC0-1.0",
})

KNOWN_TOPLEVEL_FIELDS: frozenset[str] = frozenset({
    "name",
    "description",
    "version",
    "license",
    "author",
    "agentskills_version",
    "runtimes",
    "keywords",
    "homepage",
})

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,49}$")
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)

MIN_DESCRIPTION_LEN = 50
MAX_DESCRIPTION_LEN = 500
MIN_BODY_LEN = 200
MIN_NAME_LEN = 3
MAX_NAME_LEN = 50


@dataclass(frozen=True)
class RuntimeSpec:
    entrypoint: str | None = None
    capabilities: tuple[str, ...] = ()
    requires_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manifest:
    name: str
    description: str
    version: str
    license: str
    author: str
    agentskills_version: str
    runtimes: dict[str, RuntimeSpec]
    body: str
    keywords: tuple[str, ...] = ()
    homepage: str | None = None
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None

    @classmethod
    def from_text(cls, text: str, source_path: str | None = None) -> "Manifest":
        frontmatter, body = _split_frontmatter(text)
        if frontmatter is None:
            raise ManifestParseError("file has no YAML frontmatter delimited by '---'")
        try:
            data = yaml.safe_load(frontmatter) or {}
        except yaml.YAMLError as exc:
            raise ManifestParseError(f"invalid YAML frontmatter: {exc}") from exc
        if not isinstance(data, dict):
            raise ManifestParseError("frontmatter must be a YAML mapping")

        runtimes_raw = data.get("runtimes") or {}
        runtimes: dict[str, RuntimeSpec] = {}
        if isinstance(runtimes_raw, dict):
            for key, spec in runtimes_raw.items():
                if not isinstance(spec, dict):
                    continue
                runtimes[str(key)] = RuntimeSpec(
                    entrypoint=spec.get("entrypoint"),
                    capabilities=tuple(spec.get("capabilities") or ()),
                    requires_capabilities=tuple(spec.get("requires_capabilities") or ()),
                )

        return cls(
            name=str(data.get("name", "") or ""),
            description=str(data.get("description", "") or ""),
            version=str(data.get("version", "") or ""),
            license=str(data.get("license", "") or ""),
            author=str(data.get("author", "") or ""),
            agentskills_version=str(data.get("agentskills_version", "") or ""),
            runtimes=runtimes,
            body=body,
            keywords=tuple(data.get("keywords") or ()),
            homepage=data.get("homepage"),
            raw_frontmatter=data,
            source_path=source_path,
        )

    @classmethod
    def parse(cls, path: Path) -> "Manifest":
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_text(text, source_path=str(path))


@dataclass(frozen=True)
class LintIssue:
    level: Literal["error", "warning"]
    code: str
    message: str
    path: str

    def is_error(self) -> bool:
        return self.level == "error"


class ManifestParseError(Exception):
    pass


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.lstrip().startswith("---"):
        return None, text
    match = FRONTMATTER_PATTERN.match(text.lstrip("﻿"))
    if not match:
        return None, text
    return match.group(1), match.group(2)


def lint(manifest_path: Path) -> list[LintIssue]:
    """Validate a manifest file and return all issues. Empty list = clean."""
    path_str = str(manifest_path)
    try:
        text = Path(manifest_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return [LintIssue("error", "file.missing", f"file not found: {path_str}", path_str)]

    return lint_text(text, path_str)


def lint_text(text: str, path_str: str = "<inline>") -> list[LintIssue]:
    issues: list[LintIssue] = []

    frontmatter_text, body = _split_frontmatter(text)
    if frontmatter_text is None:
        issues.append(LintIssue(
            "error", "frontmatter.missing",
            "manifest must begin with YAML frontmatter delimited by '---'", path_str,
        ))
        return issues

    try:
        data = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as exc:
        issues.append(LintIssue(
            "error", "frontmatter.invalid_yaml",
            f"invalid YAML frontmatter: {exc}", path_str,
        ))
        return issues

    if not isinstance(data, dict):
        issues.append(LintIssue(
            "error", "frontmatter.invalid_yaml",
            "frontmatter must be a YAML mapping", path_str,
        ))
        return issues

    issues.extend(_check_name(data, path_str))
    issues.extend(_check_description(data, path_str))
    issues.extend(_check_version(data, path_str))
    issues.extend(_check_license(data, path_str))
    issues.extend(_check_author(data, path_str))
    issues.extend(_check_agentskills_version(data, path_str))
    issues.extend(_check_runtimes(data, path_str))
    issues.extend(_check_body(body, path_str))
    issues.extend(_check_unknown_toplevel(data, path_str))

    return issues


def _check_name(data: dict[str, Any], path: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    name = data.get("name")
    if not name:
        issues.append(LintIssue("error", "name.missing", "missing required field 'name'", path))
        return issues
    if not isinstance(name, str) or not NAME_PATTERN.match(name):
        issues.append(LintIssue(
            "error", "name.format",
            f"name '{name}' must match {NAME_PATTERN.pattern} "
            f"(lowercase, hyphens, {MIN_NAME_LEN}-{MAX_NAME_LEN} chars)", path,
        ))
    return issues


def _check_description(data: dict[str, Any], path: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    desc = data.get("description")
    if not desc:
        issues.append(LintIssue(
            "error", "description.missing", "missing required field 'description'", path,
        ))
        return issues
    if not isinstance(desc, str):
        issues.append(LintIssue(
            "error", "description.too_short",
            "description must be a string", path,
        ))
        return issues
    if len(desc) < MIN_DESCRIPTION_LEN:
        issues.append(LintIssue(
            "error", "description.too_short",
            f"description is {len(desc)} chars; must be >= {MIN_DESCRIPTION_LEN}", path,
        ))
    if len(desc) > MAX_DESCRIPTION_LEN:
        issues.append(LintIssue(
            "error", "description.too_long",
            f"description is {len(desc)} chars; must be <= {MAX_DESCRIPTION_LEN}", path,
        ))
    return issues


def _check_version(data: dict[str, Any], path: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    version = data.get("version")
    if not version:
        issues.append(LintIssue("error", "version.missing", "missing required field 'version'", path))
        return issues
    if not isinstance(version, str) or not SEMVER_PATTERN.match(version):
        issues.append(LintIssue(
            "error", "version.format",
            f"version '{version}' is not valid semver (e.g., '0.1.0', '1.2.3-alpha')", path,
        ))
    return issues


def _check_license(data: dict[str, Any], path: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    lic = data.get("license")
    if not lic:
        issues.append(LintIssue("error", "license.missing", "missing required field 'license'", path))
        return issues
    if isinstance(lic, str) and lic not in KNOWN_LICENSES:
        issues.append(LintIssue(
            "warning", "license.unknown",
            f"license '{lic}' is not in known SPDX list "
            f"(known: {', '.join(sorted(KNOWN_LICENSES))})", path,
        ))
    return issues


def _check_author(data: dict[str, Any], path: str) -> list[LintIssue]:
    if not data.get("author"):
        return [LintIssue("error", "author.missing", "missing required field 'author'", path)]
    return []


def _check_agentskills_version(data: dict[str, Any], path: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    av = data.get("agentskills_version")
    if av is None or av == "":
        issues.append(LintIssue(
            "error", "agentskills_version.missing",
            "missing required field 'agentskills_version'", path,
        ))
        return issues
    av_str = str(av)
    if av_str not in SUPPORTED_AGENTSKILLS_VERSIONS:
        issues.append(LintIssue(
            "error", "agentskills_version.unsupported",
            f"agentskills_version '{av_str}' is not supported "
            f"(supported: {', '.join(sorted(SUPPORTED_AGENTSKILLS_VERSIONS))})", path,
        ))
    return issues


def _check_runtimes(data: dict[str, Any], path: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    runtimes = data.get("runtimes")
    if runtimes is None:
        issues.append(LintIssue(
            "error", "runtimes.missing",
            "missing required field 'runtimes' (declare hermes, openclaw, or both)", path,
        ))
        return issues
    if not isinstance(runtimes, dict) or not runtimes:
        issues.append(LintIssue(
            "error", "runtimes.empty",
            "runtimes must declare at least one of: hermes, openclaw, both", path,
        ))
        return issues

    declared_executable = [k for k in runtimes if k in {"hermes", "openclaw"}]
    has_both_block = "both" in runtimes
    if not declared_executable and not has_both_block:
        issues.append(LintIssue(
            "error", "runtimes.empty",
            "runtimes must declare at least one of: hermes, openclaw, both", path,
        ))

    for key, spec in runtimes.items():
        if key not in KNOWN_RUNTIME_KEYS:
            issues.append(LintIssue(
                "warning", "runtimes.unknown_key",
                f"unknown runtime '{key}' (known: hermes, openclaw, both)", path,
            ))
            continue
        if not isinstance(spec, dict):
            issues.append(LintIssue(
                "error", "runtime.entrypoint.missing",
                f"runtimes.{key} must be a mapping", path,
            ))
            continue
        if key in {"hermes", "openclaw"}:
            if not spec.get("entrypoint"):
                issues.append(LintIssue(
                    "error", "runtime.entrypoint.missing",
                    f"runtimes.{key}.entrypoint is required", path,
                ))
        for cap_field in ("capabilities", "requires_capabilities"):
            caps = spec.get(cap_field) or []
            if not isinstance(caps, list):
                continue
            for cap in caps:
                if cap not in KNOWN_CAPABILITIES:
                    issues.append(LintIssue(
                        "warning", "runtime.capabilities.unknown",
                        f"runtimes.{key}.{cap_field} contains unknown capability '{cap}' "
                        f"(known: {', '.join(sorted(KNOWN_CAPABILITIES))})", path,
                    ))
    return issues


def _check_body(body: str, path: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    stripped = body.strip()
    if not stripped:
        issues.append(LintIssue("error", "body.missing", "manifest body is empty", path))
        return issues
    if len(stripped) < MIN_BODY_LEN:
        issues.append(LintIssue(
            "error", "body.too_short",
            f"body is {len(stripped)} chars; must be >= {MIN_BODY_LEN}", path,
        ))
    return issues


def _check_unknown_toplevel(data: dict[str, Any], path: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for key in data:
        if key not in KNOWN_TOPLEVEL_FIELDS:
            issues.append(LintIssue(
                "warning", "clawhub.proprietary_field",
                f"unknown top-level field '{key}' — treated as advisory ClawHub extension", path,
            ))
    return issues


def discover(directory: Path) -> list[Path]:
    """Find all SKILL.md files under a directory (one level deep)."""
    base = Path(directory)
    if base.is_file() and base.name == "SKILL.md":
        return [base]
    if not base.is_dir():
        return []
    found: list[Path] = []
    direct = base / "SKILL.md"
    if direct.exists():
        found.append(direct)
    for child in sorted(base.iterdir()):
        if child.is_dir():
            candidate = child / "SKILL.md"
            if candidate.exists():
                found.append(candidate)
    return found
