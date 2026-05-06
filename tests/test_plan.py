import subprocess
from pathlib import Path

from nightshift.config import load_config
from nightshift.init import init_global
from nightshift.plan import (
    NightshiftPlan,
    ProviderBudget,
    build_plan,
    format_plan,
)
from nightshift.providers import (
    ProviderUsage,
    ProviderUsageError,
    UsageWindow,
    fetch_provider_usage_results,
)
from nightshift.repos import add_repo


def test_format_plan_snapshots_representative_provider_budget_rows() -> None:
    """Lock `_format_budget` lines for error suffix, ready, and no usable reserve."""
    plan = NightshiftPlan(
        strategy="priority",
        budgets=(
            ProviderBudget(
                provider="cursor",
                window="",
                reserve_percent=0.0,
                allocated_percent=0.0,
                reserved_percent=0.0,
                usable_percent=0.0,
                status="error: worker not configured for provider: cursor",
            ),
            ProviderBudget(
                provider="codex",
                window="weekly",
                reserve_percent=40.0,
                allocated_percent=20.0,
                reserved_percent=0.0,
                usable_percent=20.0,
                status="ready",
            ),
            ProviderBudget(
                provider="claude",
                window="weekly",
                reserve_percent=30.0,
                allocated_percent=15.0,
                reserved_percent=5.0,
                usable_percent=0.0,
                status="no usable reserve",
            ),
        ),
        repos=(),
        work=(),
    )
    rendered = format_plan(plan)
    assert (
        "  cursor unknown: 0% reserve, 0% allocated, 0% reserved, 0% usable, "
        "error: worker not configured for provider: cursor" in rendered
    )
    assert (
        "  codex weekly: 40% reserve, 20% allocated, 0% reserved, 20% usable"
        in rendered
    )
    assert ", ready" not in rendered
    assert (
        "  claude weekly: 30% reserve, 15% allocated, 5% reserved, 0% usable, "
        "no usable reserve" in rendered
    )


def test_format_plan_build_plan_usage_error_budget_line(tmp_path: Path) -> None:
    """`build_plan` + `ProviderUsageError` should match formatted budget line."""
    config_path = tmp_path / "config.toml"
    work = tmp_path / "work"
    init_global(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'workdir = "~/.nightshift/work"', f'workdir = "{work}"'
        ),
        encoding="utf-8",
    )
    config = load_config(config_path)
    plan = build_plan(config, (ProviderUsageError("codex", "no codexbar cache"),))
    rendered = format_plan(plan)
    assert (
        "  codex unknown: 0% reserve, 0% allocated, 0% reserved, 0% usable, "
        "error: no codexbar cache" in rendered
    )


def test_build_plan_allocates_reserve_to_ready_repo(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    repo = tmp_path / "repo"
    repo.mkdir()
    repo.joinpath("pyproject.toml").write_text("[project]\nname = 'repo'\n")
    init_global(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'workdir = "~/.nightshift/work"', f'workdir = "{tmp_path / "work"}"'
        ),
        encoding="utf-8",
    )
    add_repo(repo, config_path)
    config = load_config(config_path)
    usage = ProviderUsage(
        provider="codex",
        source="test",
        updated_at="2026-05-01T12:00:00Z",
        account="",
        windows=(
            UsageWindow(
                name="weekly",
                used_percent=10,
                resets_at="2026-05-05T16:00:00Z",
                reset_description="later",
                window_minutes=12000,
            ),
        ),
    )

    plan = build_plan(config, (usage,))

    assert plan.budgets[0].provider == "codex"
    assert plan.budgets[0].usable_percent == 20
    assert plan.work[0].provider == "codex"
    assert plan.work[0].repo == "repo"
    assert plan.work[0].task == "failing_tests"
    assert "codex weekly: 40% reserve" in format_plan(plan)
    assert "codex -> repo -> failing_tests" in format_plan(plan)


def test_build_plan_reports_worker_not_configured_for_usage(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    work = tmp_path / "work"
    init_global(config_path)
    config_path.write_text(
        f"""
[runtime]
workdir = "{work}"
schedule = "00:00-05:00"

[providers]
usage_source = "codexbar"
enabled = ["codex", "cursor"]

[scheduler]
strategy = "priority"
provider_order = ["cursor"]
max_workers = 2

[budget]
allocation_fraction = 0.5
reserve_floor_percent = 5
default_task_reservation_percent = 5
reservation_ttl_minutes = 90

[workers.codex]
model = ""
budget_window = "weekly"
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    usage = ProviderUsage(
        provider="cursor",
        source="test",
        updated_at="2026-05-01T12:00:00Z",
        account="",
        windows=(
            UsageWindow(
                name="Auto",
                used_percent=10,
                resets_at="2026-05-05T16:00:00Z",
                reset_description="later",
                window_minutes=12000,
            ),
        ),
    )

    plan = build_plan(config, (usage,))

    assert plan.work == ()
    rendered = format_plan(plan)
    assert (
        "  cursor unknown: 0% reserve, 0% allocated, 0% reserved, 0% usable, "
        "error: worker not configured for provider: cursor" in rendered
    )


def test_build_plan_surfaces_typo_provider_usage_errors(tmp_path: Path) -> None:
    """Unknown provider names in config should not crash planning; budget shows error."""

    def _runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="""
[
  {
    "provider": "codexx",
    "error": {"message": "unknown provider"}
  }
]
""",
            stderr="",
        )

    config_path = tmp_path / "config.toml"
    work = tmp_path / "work"
    init_global(config_path)
    config_path.write_text(
        f"""
[runtime]
workdir = "{work}"
schedule = "00:00-05:00"

[providers]
usage_source = "codexbar"
enabled = ["codexx"]

[scheduler]
strategy = "priority"
provider_order = ["codexx"]
max_workers = 2

[budget]
allocation_fraction = 0.5
reserve_floor_percent = 5
default_task_reservation_percent = 5
reservation_ttl_minutes = 90

[workers.codex]
model = ""
budget_window = "weekly"
""".strip(),
        encoding="utf-8",
    )
    config = load_config(config_path)
    usages = fetch_provider_usage_results(
        ("codexx",),
        runner=_runner,
        source="live",
    )
    plan = build_plan(config, usages)
    rendered = format_plan(plan)

    assert plan.budgets[0].provider == "codexx"
    assert "codexx" in rendered
    assert "error: unknown provider" in rendered


def test_build_plan_merges_duplicate_provider_usages_deterministically(
    tmp_path: Path,
) -> None:
    """Repeated fetch rows for one provider must not let an arbitrary last row win."""

    config_path = tmp_path / "config.toml"
    repo = tmp_path / "repo"
    repo.mkdir()
    repo.joinpath("pyproject.toml").write_text("[project]\nname = 'repo'\n")
    init_global(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            'workdir = "~/.nightshift/work"', f'workdir = "{tmp_path / "work"}"'
        ),
        encoding="utf-8",
    )
    add_repo(repo, config_path)
    config = load_config(config_path)

    def codex_usage(*, used_percent: int) -> ProviderUsage:
        return ProviderUsage(
            provider="codex",
            source="test",
            updated_at="2026-05-01T12:00:00Z",
            account="",
            windows=(
                UsageWindow(
                    name="weekly",
                    used_percent=used_percent,
                    resets_at="2026-05-05T16:00:00Z",
                    reset_description="later",
                    window_minutes=12000,
                ),
            ),
        )

    generous = codex_usage(used_percent=10)
    stingy = codex_usage(used_percent=96)
    reference = build_plan(config, (generous,))
    merged_high_first = build_plan(config, (generous, stingy))
    merged_low_first = build_plan(config, (stingy, generous))

    assert len(merged_high_first.budgets) == 1
    assert merged_high_first.budgets[0].usable_percent == reference.budgets[0].usable_percent
    assert merged_low_first.budgets[0].usable_percent == reference.budgets[0].usable_percent

    error_then_blocked = build_plan(
        config,
        (ProviderUsageError(provider="codex", message="stale fetch"), stingy),
    )
    assert error_then_blocked.budgets[0].status == "no usable reserve"
