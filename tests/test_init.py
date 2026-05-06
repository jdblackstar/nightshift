from pathlib import Path

from nightshift.context import render_context
from nightshift.init import init_global, init_repo_hints


def test_init_creates_global_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"

    result = init_global(config_path)

    assert config_path.exists()
    assert len(result.created) == 1
    assert result.skipped == ()


def test_init_is_non_destructive_by_default(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    init_global(config_path)
    config_path.write_text("custom = true\n", encoding="utf-8")

    result = init_global(config_path)

    assert config_path.read_text(encoding="utf-8") == "custom = true\n"
    assert config_path in result.skipped


def test_repo_init_creates_handoff_scaffold(tmp_path: Path) -> None:
    result = init_repo_hints(tmp_path)

    assert tmp_path.joinpath(".nightshift/context.md").exists()
    assert tmp_path.joinpath(".nightshift/skills/nightshift-handoff/SKILL.md").exists()
    assert len(result.created) == 2


def test_render_context_imports_markdown_and_skills(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    config_path = home / ".nightshift" / "config.toml"
    init_global(config_path)
    init_repo_hints(repo)
    monkeypatch.setattr(Path, "home", lambda: home)

    rendered = render_context(repo)

    assert "# Nightshift Agent Context" in rendered
    assert "TODO(nightshift)" in rendered
    assert "Nightshift Handoff" in rendered
