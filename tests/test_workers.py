from pathlib import Path

import pytest

from nightshift.cli import main
from nightshift.config import load_config
from nightshift.errors import NightshiftError
from nightshift.init import init_global
from nightshift.workers import (
    worker_budget_window,
    worker_command,
    worker_invocation,
)


def test_init_writes_explicit_workers(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    init_global(config_path)
    config = load_config(config_path)

    assert tuple(config.workers.by_provider) == ("codex", "claude", "cursor")
    assert config.workers.by_provider["codex"].budget_window == "weekly"
    assert config.workers.by_provider["claude"].budget_window == "weekly"
    assert config.workers.by_provider["cursor"].model == "composer-2"
    assert worker_budget_window("cursor", config) == "Auto"
    assert worker_budget_window("codex", config) == "weekly"


def test_worker_command_builds_codex_exec(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    init_global(config_path)
    config = load_config(config_path)

    command = worker_command("codex", config, tmp_path / "repo", "do the task")

    assert command == [
        "codex",
        "exec",
        "--cd",
        str(tmp_path / "repo"),
        "--sandbox",
        "workspace-write",
        "do the task",
    ]


def test_worker_command_builds_claude_print(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    init_global(config_path)
    config = load_config(config_path)

    command = worker_command("claude", config, tmp_path / "repo", "do the task")

    assert command == [
        "claude",
        "--print",
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "text",
        "--add-dir",
        str(tmp_path / "repo"),
        "do the task",
    ]


def test_worker_invocation_runs_claude_from_workspace(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    repo = tmp_path / "repo"
    repo.mkdir()
    init_global(config_path)
    config = load_config(config_path)

    invocation = worker_invocation("claude", config, repo, "do the task")

    assert invocation.cwd == repo.resolve()
    assert invocation.command[0] == "claude"
    assert "--add-dir" in invocation.command
    assert str(repo.resolve()) in invocation.command


def test_worker_command_builds_cursor_agent_with_configured_model(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    init_global(config_path)
    config = load_config(config_path)

    command = worker_command("cursor", config, tmp_path / "repo", "do the task")

    assert command == [
        "cursor-agent",
        "--print",
        "--trust",
        "--workspace",
        str(tmp_path / "repo"),
        "--model",
        "composer-2",
        "do the task",
    ]


def test_worker_command_omits_empty_cursor_model(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    init_global(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'model = "composer-2"', 'model = ""'
        ),
        encoding="utf-8",
    )
    config = load_config(config_path)

    command = worker_command("cursor", config, tmp_path / "repo", "do the task")

    assert command == [
        "cursor-agent",
        "--print",
        "--trust",
        "--workspace",
        str(tmp_path / "repo"),
        "do the task",
    ]


def test_worker_command_rejects_unsupported_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    init_global(config_path)
    config = load_config(config_path)

    with pytest.raises(NightshiftError, match="unsupported worker provider: unknown"):
        worker_command("unknown", config, tmp_path / "repo", "do the task")


def test_worker_command_rejects_unconfigured_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[runtime]
workdir = "~/.nightshift/work"

[workers.codex]
model = ""
budget_window = "weekly"
""",
        encoding="utf-8",
    )
    config = load_config(config_path)

    with pytest.raises(
        NightshiftError, match="worker not configured for provider: cursor"
    ):
        worker_command("cursor", config, tmp_path / "repo", "do the task")


def test_workers_command_cli_exits_on_missing_cursor_worker_config(
    tmp_path: Path, capsys
) -> None:
    config_path = tmp_path / "config.toml"
    repo = tmp_path / "repo"
    repo.mkdir()
    config_path.write_text(
        """
[runtime]
workdir = "~/.nightshift/work"

[workers.codex]
model = ""
budget_window = "weekly"
""",
        encoding="utf-8",
    )

    code = main(
        [
            "workers",
            "command",
            "cursor",
            "--repo",
            str(repo),
            "--config",
            str(config_path),
        ]
    )

    err = capsys.readouterr().err
    assert code == 1
    assert "nightshift:" in err
    assert "worker not configured for provider: cursor" in err


def test_workers_command_cli_prints_dry_run_command(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "config.toml"
    repo = tmp_path / "repo"
    repo.mkdir()
    init_global(config_path)

    code = main(
        [
            "workers",
            "command",
            "cursor",
            "--repo",
            str(repo),
            "--config",
            str(config_path),
        ]
    )

    assert code == 0
    assert capsys.readouterr().out.strip().splitlines() == [
        f"cwd: {repo}",
        (
            "command: cursor-agent --print --trust --workspace "
            f"{repo} --model composer-2 'do the task'"
        ),
    ]
