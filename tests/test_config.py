from pathlib import Path

from nightshift.config import describe_config
from nightshift.init import init_global


def test_describe_config_lists_repo_policy(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    init_global(config_path)

    rendered = describe_config(config_path)

    assert f"Config: {config_path}" in rendered
    assert "Schedule: 00:00-05:00" in rendered
    assert "Pull requests:" in rendered
    assert "enabled: yes" in rendered
    assert "Providers:" in rendered
    assert "  - codex\n  - claude\n  - cursor" in rendered
    assert "Scheduler:" in rendered
    assert "strategy: priority" in rendered
    assert "Budget:" in rendered
    assert "default_task_reservation_percent: 5.0" in rendered
    assert "Workers:" in rendered
    assert "codex: model=, budget_window=weekly" in rendered
    assert "claude: model=, budget_window=weekly" in rendered
    assert "cursor: model=composer-2, budget_window=Auto" in rendered
    assert "Allowed work:" in rendered
    assert "failing_tests" in rendered
    assert "Repos:" in rendered
