from pathlib import Path

from nightshift.cli import main
from nightshift.config import load_config
from nightshift.repos import add_repo, remove_repo, set_repo_enabled


def test_add_repo_creates_config_and_repo_entry(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    repo.joinpath("pyproject.toml").write_text(
        '[project]\nname = "project"\n', encoding="utf-8"
    )
    config_path = tmp_path / "config.toml"

    change = add_repo(repo, config_path)
    config = load_config(config_path)

    assert change.action == "added"
    assert change.repo.name == "project"
    assert change.repo.test_command == "uv run pytest"
    assert change.repo.lint_command == "uv run ruff check ."
    assert change.repo.typecheck_command == ""
    assert change.repo.format_check_command == "uv run ruff format --check ."
    assert config.repos[0].path == repo.resolve()


def test_add_repo_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    config_path = tmp_path / "config.toml"

    add_repo(repo, config_path)
    change = add_repo(repo, config_path)
    config = load_config(config_path)

    assert change.action == "exists"
    assert len(config.repos) == 1


def test_repo_enable_disable_and_remove(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    config_path = tmp_path / "config.toml"
    add_repo(repo, config_path)

    disabled = set_repo_enabled("project", False, config_path)
    assert disabled.repo.enabled is False
    assert load_config(config_path).repos[0].enabled is False

    enabled = set_repo_enabled("project", True, config_path)
    assert enabled.repo.enabled is True
    assert load_config(config_path).repos[0].enabled is True

    removed = remove_repo("project", config_path)
    assert removed.repo.name == "project"
    assert load_config(config_path).repos == ()


def test_repo_rewrite_preserves_sections_after_repos(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    config_path = tmp_path / "config.toml"
    add_repo(repo, config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + """

[future]
keep = "yes"
""",
        encoding="utf-8",
    )

    set_repo_enabled("project", False, config_path)

    text = config_path.read_text(encoding="utf-8")
    assert "[future]" in text
    assert 'keep = "yes"' in text
    assert "enabled = false" in text


def test_repos_add_cli_prints_short_status(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    config_path = tmp_path / "config.toml"

    code = main(["repos", "add", str(repo), "--config", str(config_path)])

    assert code == 0
    assert capsys.readouterr().out.strip() == (
        f"added project to {config_path.resolve()}"
    )
