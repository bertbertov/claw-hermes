"""Tests for the ``claw-hermes skill`` subcommand group."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from claw_hermes.cli import main
from claw_hermes import manifest as m


def test_skill_lint_clean_repo_skill() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    skill_dir = repo_root / "skill"
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "lint", str(skill_dir)])
    assert result.exit_code == 0, result.output


def test_skill_lint_clean_hello_world_example() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    example_dir = repo_root / "examples" / "skills" / "hello-world"
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "lint", str(example_dir)])
    assert result.exit_code == 0, result.output


def test_skill_lint_returns_exit_2_on_errors(tmp_path: Path) -> None:
    bad_skill = tmp_path / "SKILL.md"
    bad_skill.write_text("no frontmatter at all\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "lint", str(bad_skill)])
    assert result.exit_code == 2


def test_skill_lint_returns_exit_1_on_warnings_only(tmp_path: Path) -> None:
    fm = (
        "---\n"
        "name: warn-skill\n"
        "description: Description that is comfortably longer than the fifty-character minimum so the "
        "linter does not flag it for being too short at all.\n"
        "version: 0.1.0\n"
        "license: WTFPL-7.0\n"
        "author: Tester\n"
        'agentskills_version: "1.0"\n'
        "runtimes:\n"
        "  hermes:\n"
        "    entrypoint: python -m demo\n"
        "---\n"
    )
    body = (
        "Body is comfortably above the two hundred character minimum required by the linter "
        "so that no body.too_short error fires for this fixture. The only intended issue here "
        "is the unknown SPDX license, which fires a warning only.\n"
    )
    skill = tmp_path / "SKILL.md"
    skill.write_text(fm + body, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "lint", str(skill)])
    assert result.exit_code == 1, result.output


def test_skill_lint_strict_promotes_warnings_to_errors(tmp_path: Path) -> None:
    fm = (
        "---\n"
        "name: warn-skill\n"
        "description: Description that is comfortably longer than the fifty-character minimum so the "
        "linter does not flag it for being too short at all.\n"
        "version: 0.1.0\n"
        "license: WTFPL-7.0\n"
        "author: Tester\n"
        'agentskills_version: "1.0"\n'
        "runtimes:\n"
        "  hermes:\n"
        "    entrypoint: python -m demo\n"
        "---\n"
    )
    body = (
        "Body is comfortably above the two hundred character minimum required by the linter "
        "so that no body.too_short error fires for this fixture. The only intended issue here "
        "is the unknown SPDX license, which fires a warning only.\n"
    )
    skill = tmp_path / "SKILL.md"
    skill.write_text(fm + body, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["skill", "lint", str(skill), "--strict"])
    assert result.exit_code == 2, result.output


def test_skill_lint_json_output(tmp_path: Path) -> None:
    bad_skill = tmp_path / "SKILL.md"
    bad_skill.write_text("no frontmatter\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(main, ["skill", "lint", str(bad_skill), "--json"])
    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["errors"] >= 1
    assert any(i["code"] == "frontmatter.missing" for i in payload["issues"])


def test_skill_new_default_both_runtime_lints_clean(tmp_path: Path) -> None:
    runner = CliRunner()
    target = tmp_path / "demo-skill"
    result = runner.invoke(
        main,
        [
            "skill", "new", str(target),
            "--runtime", "both",
            "--description", "A scaffolded skill used by the test suite to verify the linter passes.",
            "--author", "Tester",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (target / "SKILL.md").exists()
    issues = m.lint(target / "SKILL.md")
    assert [i for i in issues if i.is_error()] == []
    parsed = m.Manifest.parse(target / "SKILL.md")
    assert "hermes" in parsed.runtimes
    assert "openclaw" in parsed.runtimes


def test_skill_new_hermes_only_lints_clean(tmp_path: Path) -> None:
    runner = CliRunner()
    target = tmp_path / "hermes-only"
    result = runner.invoke(
        main,
        [
            "skill", "new", str(target),
            "--runtime", "hermes",
            "--description", "A scaffolded hermes-only skill used by the test suite to verify lint passes.",
            "--author", "Tester",
        ],
    )
    assert result.exit_code == 0, result.output
    parsed = m.Manifest.parse(target / "SKILL.md")
    assert "hermes" in parsed.runtimes
    assert "openclaw" not in parsed.runtimes


def test_skill_new_openclaw_only_lints_clean(tmp_path: Path) -> None:
    runner = CliRunner()
    target = tmp_path / "openclaw-only"
    result = runner.invoke(
        main,
        [
            "skill", "new", str(target),
            "--runtime", "openclaw",
            "--description", "A scaffolded openclaw-only skill used by the test suite to verify lint passes.",
            "--author", "Tester",
        ],
    )
    assert result.exit_code == 0, result.output
    parsed = m.Manifest.parse(target / "SKILL.md")
    assert "openclaw" in parsed.runtimes
    assert "hermes" not in parsed.runtimes


def test_skill_new_refuses_to_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "skill", "new", str(target),
            "--runtime", "both",
            "--description", "Description that is long enough to pass the description minimum length check.",
            "--author", "Tester",
        ],
    )
    assert result.exit_code == 1
    assert "refusing to overwrite" in result.output


def test_skill_list_summarises_each_skill(tmp_path: Path) -> None:
    runner = CliRunner()
    a = tmp_path / "alpha"
    b = tmp_path / "beta"
    runner.invoke(main, [
        "skill", "new", str(a), "--runtime", "both",
        "--description", "Alpha skill description that is long enough to pass the linter check.",
        "--author", "Tester",
    ])
    runner.invoke(main, [
        "skill", "new", str(b), "--runtime", "hermes",
        "--description", "Beta skill description that is long enough to pass the linter check.",
        "--author", "Tester",
    ])

    result = runner.invoke(main, ["skill", "list", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "alpha" in result.output
    assert "beta" in result.output
    assert "v0.1.0" in result.output


def test_skill_lint_directory_with_multiple_skills(tmp_path: Path) -> None:
    runner = CliRunner()
    a = tmp_path / "alpha"
    b = tmp_path / "beta"
    runner.invoke(main, [
        "skill", "new", str(a), "--runtime", "both",
        "--description", "Alpha skill description that is long enough to pass the linter check.",
        "--author", "Tester",
    ])
    runner.invoke(main, [
        "skill", "new", str(b), "--runtime", "openclaw",
        "--description", "Beta skill description that is long enough to pass the linter check.",
        "--author", "Tester",
    ])
    result = runner.invoke(main, ["skill", "lint", str(tmp_path)])
    assert result.exit_code == 0, result.output
