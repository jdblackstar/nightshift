import subprocess
from pathlib import Path

import pytest

from nightshift.cli import main
from nightshift.doctor import FAIL, OK, WARN, doctor_passed, run_doctor
from nightshift.init import init_global


def test_doctor_fails_when_config_is_missing(tmp_path: Path) -> None:
    checks = run_doctor(tmp_path / "missing.toml", check_auth=False)

    assert checks[0].status == FAIL
    assert not doctor_passed(checks)


def test_doctor_checks_config_repos_clis_cache_and_workdir(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "config.toml"
    repo = tmp_path / "repo"
    workdir = tmp_path / "work"
    repo.mkdir()
    init_global(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'workdir = "~/.nightshift/work"', f'workdir = "{workdir}"'
        )
        + f"""

[[repos]]
name = "repo"
path = "{repo}"
enabled = true
priority = 50

[repos.commands]
test = "uv run pytest"
lint = ""
typecheck = ""
format_check = ""
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "nightshift.doctor.shutil.which", lambda command: f"/bin/{command}"
    )
    monkeypatch.setattr(
        "nightshift.doctor.fetch_cached_provider_usage", lambda provider: None
    )

    checks = run_doctor(config_path, check_auth=False)

    assert doctor_passed(checks)
    assert ("config", OK) in {(check.name, check.status) for check in checks}
    assert ("repo repo", OK) in {(check.name, check.status) for check in checks}
    assert ("codexbar cache", WARN) in {(check.name, check.status) for check in checks}
    assert workdir.exists()


def test_doctor_warns_on_unknown_provider_name(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    workdir = tmp_path / "work"
    init_global(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        .replace(
            'enabled = ["codex", "claude", "cursor"]',
            'enabled = ["codex", "claude", "cursor", "bogus"]',
        )
        .replace(
            'workdir = "~/.nightshift/work"',
            f'workdir = "{workdir}"',
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "nightshift.doctor.shutil.which", lambda command: f"/bin/{command}"
    )
    monkeypatch.setattr(
        "nightshift.doctor.fetch_cached_provider_usage", lambda provider: None
    )

    checks = run_doctor(config_path, check_auth=False)

    assert ("provider bogus", WARN) in {
        (check.name, check.status) for check in checks
    }
    assert doctor_passed(checks)


def test_doctor_help_documents_fail_on_unknown_providers(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["doctor", "--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--fail-on-unknown-providers" in out
    assert "CI" in out or "automation" in out


def test_doctor_fails_on_unknown_provider_when_strict(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "config.toml"
    workdir = tmp_path / "work"
    init_global(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        .replace(
            'enabled = ["codex", "claude", "cursor"]',
            'enabled = ["codex", "claude", "cursor", "bogus"]',
        )
        .replace(
            'workdir = "~/.nightshift/work"',
            f'workdir = "{workdir}"',
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "nightshift.doctor.shutil.which", lambda command: f"/bin/{command}"
    )
    monkeypatch.setattr(
        "nightshift.doctor.fetch_cached_provider_usage", lambda provider: None
    )

    checks = run_doctor(
        config_path, check_auth=False, fail_on_unknown_providers=True
    )

    assert ("provider bogus", FAIL) in {
        (check.name, check.status) for check in checks
    }
    assert not doctor_passed(checks)


def test_doctor_can_check_github_auth(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.toml"
    workdir = tmp_path / "work"
    init_global(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'workdir = "~/.nightshift/work"', f'workdir = "{workdir}"'
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "nightshift.doctor.shutil.which", lambda command: f"/bin/{command}"
    )
    monkeypatch.setattr(
        "nightshift.doctor.fetch_cached_provider_usage", lambda provider: None
    )

    monkeypatch.setattr(
        "nightshift.doctor._run",
        lambda args: subprocess.CompletedProcess(args, 0, stdout="ok", stderr=""),
    )

    checks = run_doctor(config_path)

    assert ("github auth", OK) in {(check.name, check.status) for check in checks}
