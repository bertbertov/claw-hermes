"""Tests for claw_hermes.manifest — schema parser + linter.

Each lint rule has a positive test (rule fires on bad input) and a negative test (rule does
not fire on good input). Fixtures are inline strings so tests run with no filesystem outside
``tmp_path``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from claw_hermes import manifest as m


GOOD_BODY = (
    "# Sample skill\n\n"
    "This is a fully realised skill body that is comfortably above the two hundred character "
    "minimum that the body length linter enforces. It exists as a reusable fixture for the "
    "positive cases in this test module and intentionally describes nothing in particular.\n"
)


def _good_frontmatter(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "good-skill",
        "description": (
            "A perfectly fine skill manifest used as the positive baseline for the linter test "
            "suite. It is long enough to clear the description minimum length check."
        ),
        "version": "0.1.0",
        "license": "MIT",
        "author": "Tester",
        "agentskills_version": "1.0",
        "runtimes": {
            "hermes": {"entrypoint": "python -m demo", "capabilities": ["memory.recall"]},
        },
    }
    base.update(overrides)
    return base


def _render(frontmatter: dict[str, object], body: str = GOOD_BODY) -> str:
    import yaml
    return "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body


def _codes(issues: list[m.LintIssue]) -> set[str]:
    return {i.code for i in issues}


# ---- Manifest.parse round trip ------------------------------------------------------------


def test_manifest_parse_round_trip(tmp_path: Path) -> None:
    text = _render(_good_frontmatter())
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(text, encoding="utf-8")

    manifest = m.Manifest.parse(skill_path)

    assert manifest.name == "good-skill"
    assert manifest.version == "0.1.0"
    assert manifest.license == "MIT"
    assert manifest.author == "Tester"
    assert manifest.agentskills_version == "1.0"
    assert "hermes" in manifest.runtimes
    assert manifest.runtimes["hermes"].entrypoint == "python -m demo"
    assert manifest.runtimes["hermes"].capabilities == ("memory.recall",)
    assert manifest.body.strip().startswith("# Sample skill")
    assert manifest.source_path == str(skill_path)


def test_manifest_from_text_no_frontmatter_raises() -> None:
    with pytest.raises(m.ManifestParseError):
        m.Manifest.from_text("just a markdown body, no frontmatter at all")


def test_manifest_from_text_invalid_yaml_raises() -> None:
    with pytest.raises(m.ManifestParseError):
        m.Manifest.from_text("---\nname: [unclosed\n---\nbody")


# ---- frontmatter rules --------------------------------------------------------------------


def test_frontmatter_missing_fires() -> None:
    issues = m.lint_text("just a body, no frontmatter delimiters\n")
    assert "frontmatter.missing" in _codes(issues)


def test_frontmatter_missing_does_not_fire_on_valid_manifest() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "frontmatter.missing" not in _codes(issues)


def test_frontmatter_invalid_yaml_fires() -> None:
    issues = m.lint_text("---\nname: [oops\n---\n" + GOOD_BODY)
    assert "frontmatter.invalid_yaml" in _codes(issues)


def test_frontmatter_invalid_yaml_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "frontmatter.invalid_yaml" not in _codes(issues)


# ---- name rules ---------------------------------------------------------------------------


def test_name_missing_fires() -> None:
    fm = _good_frontmatter()
    del fm["name"]
    issues = m.lint_text(_render(fm))
    assert "name.missing" in _codes(issues)


def test_name_missing_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "name.missing" not in _codes(issues)


def test_name_format_fires_on_uppercase() -> None:
    issues = m.lint_text(_render(_good_frontmatter(name="BadName")))
    assert "name.format" in _codes(issues)


def test_name_format_fires_on_too_short() -> None:
    issues = m.lint_text(_render(_good_frontmatter(name="ab")))
    assert "name.format" in _codes(issues)


def test_name_format_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter(name="my-cool-skill")))
    assert "name.format" not in _codes(issues)


# ---- description rules --------------------------------------------------------------------


def test_description_missing_fires() -> None:
    fm = _good_frontmatter()
    del fm["description"]
    issues = m.lint_text(_render(fm))
    assert "description.missing" in _codes(issues)


def test_description_missing_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "description.missing" not in _codes(issues)


def test_description_too_short_fires() -> None:
    issues = m.lint_text(_render(_good_frontmatter(description="too short")))
    assert "description.too_short" in _codes(issues)


def test_description_too_short_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "description.too_short" not in _codes(issues)


# ---- version rules ------------------------------------------------------------------------


def test_version_missing_fires() -> None:
    fm = _good_frontmatter()
    del fm["version"]
    issues = m.lint_text(_render(fm))
    assert "version.missing" in _codes(issues)


def test_version_missing_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "version.missing" not in _codes(issues)


def test_version_format_fires_on_non_semver() -> None:
    issues = m.lint_text(_render(_good_frontmatter(version="v1")))
    assert "version.format" in _codes(issues)


def test_version_format_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter(version="1.2.3-alpha.1")))
    assert "version.format" not in _codes(issues)


# ---- license rules ------------------------------------------------------------------------


def test_license_missing_fires() -> None:
    fm = _good_frontmatter()
    del fm["license"]
    issues = m.lint_text(_render(fm))
    assert "license.missing" in _codes(issues)


def test_license_missing_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "license.missing" not in _codes(issues)


def test_license_unknown_fires_warning() -> None:
    issues = m.lint_text(_render(_good_frontmatter(license="WTFPL-7.0")))
    codes = _codes(issues)
    assert "license.unknown" in codes
    warning_codes = {i.code for i in issues if i.level == "warning"}
    assert "license.unknown" in warning_codes


def test_license_unknown_does_not_fire_on_known_license() -> None:
    issues = m.lint_text(_render(_good_frontmatter(license="Apache-2.0")))
    assert "license.unknown" not in _codes(issues)


# ---- agentskills_version rules ------------------------------------------------------------


def test_agentskills_version_missing_fires() -> None:
    fm = _good_frontmatter()
    del fm["agentskills_version"]
    issues = m.lint_text(_render(fm))
    assert "agentskills_version.missing" in _codes(issues)


def test_agentskills_version_missing_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "agentskills_version.missing" not in _codes(issues)


def test_agentskills_version_unsupported_fires() -> None:
    issues = m.lint_text(_render(_good_frontmatter(agentskills_version="2.0")))
    assert "agentskills_version.unsupported" in _codes(issues)


def test_agentskills_version_unsupported_does_not_fire_on_supported() -> None:
    issues = m.lint_text(_render(_good_frontmatter(agentskills_version="1.0")))
    assert "agentskills_version.unsupported" not in _codes(issues)


# ---- runtimes rules -----------------------------------------------------------------------


def test_runtimes_missing_fires() -> None:
    fm = _good_frontmatter()
    del fm["runtimes"]
    issues = m.lint_text(_render(fm))
    assert "runtimes.missing" in _codes(issues)


def test_runtimes_missing_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "runtimes.missing" not in _codes(issues)


def test_runtimes_empty_fires() -> None:
    issues = m.lint_text(_render(_good_frontmatter(runtimes={})))
    assert "runtimes.empty" in _codes(issues)


def test_runtimes_empty_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "runtimes.empty" not in _codes(issues)


def test_runtimes_unknown_key_fires_warning() -> None:
    bogus = {
        "hermes": {"entrypoint": "python -m demo"},
        "deno": {"entrypoint": "deno run main.ts"},
    }
    issues = m.lint_text(_render(_good_frontmatter(runtimes=bogus)))
    assert "runtimes.unknown_key" in _codes(issues)
    assert any(i.level == "warning" and i.code == "runtimes.unknown_key" for i in issues)


def test_runtimes_unknown_key_does_not_fire_on_canonical_keys() -> None:
    canonical = {
        "hermes": {"entrypoint": "python -m demo"},
        "openclaw": {"entrypoint": "node ./index.js"},
        "both": {"requires_capabilities": ["github"]},
    }
    issues = m.lint_text(_render(_good_frontmatter(runtimes=canonical)))
    assert "runtimes.unknown_key" not in _codes(issues)


def test_runtime_entrypoint_missing_fires() -> None:
    rt = {"hermes": {"capabilities": ["memory.recall"]}}
    issues = m.lint_text(_render(_good_frontmatter(runtimes=rt)))
    assert "runtime.entrypoint.missing" in _codes(issues)


def test_runtime_entrypoint_missing_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "runtime.entrypoint.missing" not in _codes(issues)


def test_runtime_capabilities_unknown_fires_warning() -> None:
    rt = {"hermes": {"entrypoint": "python -m demo", "capabilities": ["chaos.summon"]}}
    issues = m.lint_text(_render(_good_frontmatter(runtimes=rt)))
    assert "runtime.capabilities.unknown" in _codes(issues)
    assert any(i.level == "warning" and i.code == "runtime.capabilities.unknown" for i in issues)


def test_runtime_capabilities_unknown_does_not_fire_on_known() -> None:
    rt = {"hermes": {"entrypoint": "python -m demo", "capabilities": ["github", "memory.recall"]}}
    issues = m.lint_text(_render(_good_frontmatter(runtimes=rt)))
    assert "runtime.capabilities.unknown" not in _codes(issues)


# ---- body rules ---------------------------------------------------------------------------


def test_body_missing_fires() -> None:
    issues = m.lint_text(_render(_good_frontmatter(), body=""))
    assert "body.missing" in _codes(issues)


def test_body_missing_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "body.missing" not in _codes(issues)


def test_body_too_short_fires() -> None:
    issues = m.lint_text(_render(_good_frontmatter(), body="too short body\n"))
    assert "body.too_short" in _codes(issues)


def test_body_too_short_does_not_fire_on_valid() -> None:
    issues = m.lint_text(_render(_good_frontmatter()))
    assert "body.too_short" not in _codes(issues)


# ---- ClawHub proprietary fields warning --------------------------------------------------


def test_clawhub_proprietary_field_fires_warning() -> None:
    fm = _good_frontmatter()
    fm["clawhub_secret_sauce"] = "yes"
    issues = m.lint_text(_render(fm))
    assert "clawhub.proprietary_field" in _codes(issues)
    assert any(i.level == "warning" and i.code == "clawhub.proprietary_field" for i in issues)


def test_clawhub_proprietary_field_does_not_fire_on_known_fields() -> None:
    fm = _good_frontmatter(keywords=["a", "b"], homepage="https://example.com")
    issues = m.lint_text(_render(fm))
    assert "clawhub.proprietary_field" not in _codes(issues)


# ---- aggregate sanity check ---------------------------------------------------------------


def test_repo_skill_lints_clean() -> None:
    """The repo's own skill/SKILL.md must lint with zero errors after the v0.2 bootstrap."""
    repo_skill = Path(__file__).resolve().parent.parent / "skill" / "SKILL.md"
    issues = m.lint(repo_skill)
    errors = [i for i in issues if i.is_error()]
    assert errors == [], f"unexpected errors in repo skill: {errors}"


def test_example_hello_world_lints_clean() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    example = repo_root / "examples" / "skills" / "hello-world" / "SKILL.md"
    issues = m.lint(example)
    errors = [i for i in issues if i.is_error()]
    assert errors == [], f"unexpected errors in hello-world example: {errors}"
