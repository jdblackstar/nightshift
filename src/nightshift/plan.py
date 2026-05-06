from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, assert_never

from nightshift.config import NightshiftConfig, RepoConfig
from nightshift.providers import (
    ProviderUsage,
    ProviderUsageError,
    ProviderUsageResult,
    remaining_percent,
    reserve_percent,
)
from nightshift.reservations import reserved_percent


@dataclass(frozen=True)
class ProviderBudget:
    provider: str
    window: str
    reserve_percent: float
    allocated_percent: float
    reserved_percent: float
    usable_percent: float
    status: str


@dataclass(frozen=True)
class PlannedWork:
    provider: str
    repo: str
    task: str
    command: str


@dataclass(frozen=True)
class NightshiftPlan:
    strategy: str
    budgets: tuple[ProviderBudget, ...]
    repos: tuple[RepoConfig, ...]
    work: tuple[PlannedWork, ...]


def build_plan(
    config: NightshiftConfig,
    usages: Sequence[ProviderUsageResult],
) -> NightshiftPlan:
    budgets_raw = tuple(_provider_budget(config, usage) for usage in usages)
    budgets = _dedupe_budgets_by_provider(budgets_raw)
    enabled_repos = tuple(
        sorted(
            (repo for repo in config.repos if repo.enabled and repo.path.exists()),
            key=lambda repo: repo.priority,
            reverse=True,
        )
    )
    work = _planned_work(config, budgets, enabled_repos)
    return NightshiftPlan(
        strategy=config.scheduler.strategy,
        budgets=budgets,
        repos=enabled_repos,
        work=work,
    )


def _dedupe_budgets_by_provider(
    budgets: Sequence[ProviderBudget],
) -> tuple[ProviderBudget, ...]:
    chosen: dict[str, ProviderBudget] = {}
    order: list[str] = []
    for b in budgets:
        a = chosen.get(b.provider)
        if a is None:
            chosen[b.provider] = b
            order.append(b.provider)
            continue
        if b.usable_percent > a.usable_percent:
            chosen[b.provider] = b
        elif b.usable_percent < a.usable_percent:
            pass
        else:
            a_err = a.status.startswith("error:")
            b_err = b.status.startswith("error:")
            if a_err and not b_err:
                chosen[b.provider] = b
    return tuple(chosen[p] for p in order)


def format_plan(plan: NightshiftPlan) -> str:
    lines = [f"strategy: {plan.strategy}", "", "budget:"]
    if plan.budgets:
        lines.extend(f"  {_format_budget(budget)}" for budget in plan.budgets)
    else:
        lines.append("  (none)")

    lines.extend(["", "repos:"])
    if plan.repos:
        lines.extend(
            f"  {repo.name}: enabled, priority {repo.priority}, path={repo.path}"
            for repo in plan.repos
        )
    else:
        lines.append("  (none ready)")

    lines.extend(["", "would run:"])
    if plan.work:
        lines.extend(
            f"  {item.provider} -> {item.repo} -> {item.task} ({item.command})"
            for item in plan.work
        )
    else:
        lines.append("  (nothing selected)")
    return "\n".join(lines)


def _provider_budget(
    config: NightshiftConfig,
    usage: ProviderUsageResult,
) -> ProviderBudget:
    match usage:
        case ProviderUsageError(message=msg, provider=name):
            return ProviderBudget(
                provider=name,
                window="",
                reserve_percent=0,
                allocated_percent=0,
                reserved_percent=0,
                usable_percent=0,
                status=f"error: {msg}",
            )
        case ProviderUsage() as u:
            pass
        case _:
            assert_never(usage)

    if u.provider not in config.workers.by_provider:
        return ProviderBudget(
            provider=u.provider,
            window="",
            reserve_percent=0,
            allocated_percent=0,
            reserved_percent=0,
            usable_percent=0,
            status=f"error: worker not configured for provider: {u.provider}",
        )

    worker = config.workers.get(u.provider)

    window = next(
        (w for w in u.windows if w.name == worker.budget_window),
        None,
    )
    if window is None:
        return ProviderBudget(
            provider=u.provider,
            window="",
            reserve_percent=0,
            allocated_percent=0,
            reserved_percent=0,
            usable_percent=0,
            status=(
                "error: budget window missing: "
                f"{u.provider}/{worker.budget_window}"
            ),
        )

    reserve = reserve_percent(window, u.updated_at)
    allocated = reserve * config.budget.allocation_fraction
    state_root = config.workdir / "state"
    held = (
        reserved_percent(state_root, u.provider, window.name)
        if state_root.exists()
        else 0
    )
    usable = max(0, allocated - held)
    if remaining_percent(window) <= config.budget.reserve_floor_percent:
        usable = 0
    return ProviderBudget(
        provider=u.provider,
        window=window.name,
        reserve_percent=reserve,
        allocated_percent=allocated,
        reserved_percent=held,
        usable_percent=usable,
        status="ready" if usable > 0 else "no usable reserve",
    )


def _planned_work(
    config: NightshiftConfig,
    budgets: Sequence[ProviderBudget],
    repos: Sequence[RepoConfig],
) -> tuple[PlannedWork, ...]:
    available = {
        budget.provider: budget
        for budget in budgets
        if budget.usable_percent >= config.budget.default_task_reservation_percent
    }
    selected: list[PlannedWork] = []
    used_repos: set[str] = set()
    for provider in config.scheduler.provider_order:
        if provider not in available:
            continue
        for repo in repos:
            if len(selected) >= config.scheduler.max_workers:
                return tuple(selected)
            if repo.name in used_repos:
                continue
            task = _first_task(repo)
            if task is None:
                continue
            selected.append(
                PlannedWork(
                    provider=provider,
                    repo=repo.name,
                    task=task[0],
                    command=task[1],
                )
            )
            used_repos.add(repo.name)
            break
    return tuple(selected)


def _first_task(repo: RepoConfig) -> tuple[str, str] | None:
    candidates = (
        ("failing_tests", repo.test_command),
        ("lint_errors", repo.lint_command),
        ("type_errors", repo.typecheck_command),
        ("formatting", repo.format_check_command),
    )
    return next(((name, command) for name, command in candidates if command), None)


def _format_budget(budget: ProviderBudget) -> str:
    if budget.status != "ready" and budget.usable_percent == 0:
        suffix = f", {budget.status}" if budget.status else ""
    else:
        suffix = ""
    window = budget.window or "unknown"
    return (
        f"{budget.provider} {window}: {_percent(budget.reserve_percent)} reserve, "
        f"{_percent(budget.allocated_percent)} allocated, "
        f"{_percent(budget.reserved_percent)} reserved, "
        f"{_percent(budget.usable_percent)} usable{suffix}"
    )


def _percent(value: float) -> str:
    rounded = float(round(value, 1))
    if rounded.is_integer():
        return f"{int(rounded)}%"
    return f"{rounded}%"
