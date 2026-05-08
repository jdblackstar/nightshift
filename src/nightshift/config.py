from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


CONFIG_DIR = ".nightshift"
GLOBAL_CONFIG_FILE = "config.toml"


@dataclass(frozen=True)
class PullRequestPolicy:
    enabled: bool
    draft: bool
    base_branch: str
    max_open_per_repo: int
    delete_branch_on_close: bool


@dataclass(frozen=True)
class Guardrails:
    allowed_work: tuple[str, ...]
    blocked_paths: tuple[str, ...]


@dataclass(frozen=True)
class Signals:
    comment_tags: tuple[str, ...]
    github_labels: tuple[str, ...]


@dataclass(frozen=True)
class ContextImports:
    markdown: tuple[str, ...]
    skills: tuple[str, ...]


@dataclass(frozen=True)
class ProvidersConfig:
    enabled: tuple[str, ...]
    usage_source: str


@dataclass(frozen=True)
class SchedulerConfig:
    strategy: str
    provider_order: tuple[str, ...]
    max_workers: int


@dataclass(frozen=True)
class BudgetConfig:
    allocation_fraction: float
    reserve_floor_percent: float
    default_task_reservation_percent: float
    reservation_ttl_minutes: int


@dataclass(frozen=True)
class WorkerConfig:
    provider: str
    model: str
    budget_window: str


@dataclass(frozen=True)
class WorkersConfig:
    by_provider: dict[str, WorkerConfig]


@dataclass(frozen=True)
class RepoConfig:
    name: str
    path: Path
    enabled: bool
    priority: int
    test_command: str
    lint_command: str
    typecheck_command: str
    format_check_command: str


@dataclass(frozen=True)
class NightshiftConfig:
    config_path: Path
    workdir: Path
    schedule: str
    pull_requests: PullRequestPolicy
    guardrails: Guardrails
    signals: Signals
    context: ContextImports
    providers: ProvidersConfig
    scheduler: SchedulerConfig
    budget: BudgetConfig
    workers: WorkersConfig
    repos: tuple[RepoConfig, ...]


def default_config_dir() -> Path:
    return Path.home() / CONFIG_DIR


def default_config_path() -> Path:
    return default_config_dir() / GLOBAL_CONFIG_FILE


def load_config(config_path: Path | None = None) -> NightshiftConfig:
    path = (config_path or default_config_path()).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `nightshift init` first.")

    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)

    runtime = data.get("runtime", {})
    pull_requests = data.get("pull_requests", {})
    guardrails = data.get("guardrails", {})
    signals = data.get("signals", {})
    context = data.get("context", {})
    providers = data.get("providers", {})
    scheduler = data.get("scheduler", {})
    budget = data.get("budget", {})
    workers = data.get("workers", {})

    return NightshiftConfig(
        config_path=path,
        workdir=Path(str(runtime.get("workdir", "~/.nightshift/work"))).expanduser(),
        schedule=str(runtime.get("schedule", "00:00-05:00")),
        pull_requests=PullRequestPolicy(
            enabled=bool(pull_requests.get("enabled", True)),
            draft=bool(pull_requests.get("draft", True)),
            base_branch=str(pull_requests.get("base_branch", "main")),
            max_open_per_repo=int(pull_requests.get("max_open_per_repo", 1)),
            delete_branch_on_close=bool(
                pull_requests.get("delete_branch_on_close", True)
            ),
        ),
        guardrails=Guardrails(
            allowed_work=tuple(guardrails.get("allowed_work", ())),
            blocked_paths=tuple(guardrails.get("blocked_paths", ())),
        ),
        signals=Signals(
            comment_tags=tuple(signals.get("comment_tags", ())),
            github_labels=tuple(signals.get("github_labels", ())),
        ),
        context=ContextImports(
            markdown=tuple(context.get("imports", ())),
            skills=tuple(context.get("skills", ())),
        ),
        providers=ProvidersConfig(
            enabled=tuple(providers.get("enabled", ("codex", "claude", "cursor"))),
            usage_source=str(providers.get("usage_source", "codexbar")),
        ),
        scheduler=SchedulerConfig(
            strategy=str(scheduler.get("strategy", "priority")),
            provider_order=tuple(
                scheduler.get("provider_order", ("codex", "claude", "cursor"))
            ),
            max_workers=int(scheduler.get("max_workers", 2)),
        ),
        budget=BudgetConfig(
            allocation_fraction=float(budget.get("allocation_fraction", 0.5)),
            reserve_floor_percent=float(budget.get("reserve_floor_percent", 5)),
            default_task_reservation_percent=float(
                budget.get("default_task_reservation_percent", 5)
            ),
            reservation_ttl_minutes=int(budget.get("reservation_ttl_minutes", 90)),
        ),
        workers=WorkersConfig(by_provider=_parse_workers(workers)),
        repos=tuple(_parse_repos(data.get("repos", ()))),
    )


def describe_config(config_path: Path | None = None) -> str:
    config = load_config(config_path)
    lines = [
        f"Config: {config.config_path}",
        f"Workdir: {config.workdir}",
        f"Schedule: {config.schedule}",
        "",
        "Pull requests:",
        f"  enabled: {'yes' if config.pull_requests.enabled else 'no'}",
        f"  draft: {'yes' if config.pull_requests.draft else 'no'}",
        f"  base_branch: {config.pull_requests.base_branch}",
        f"  max_open_per_repo: {config.pull_requests.max_open_per_repo}",
        "",
        "Providers:",
        f"  usage_source: {config.providers.usage_source}",
        *[f"  - {provider}" for provider in config.providers.enabled],
        "",
        "Scheduler:",
        f"  strategy: {config.scheduler.strategy}",
        f"  provider_order: {' -> '.join(config.scheduler.provider_order)}",
        f"  max_workers: {config.scheduler.max_workers}",
        "",
        "Budget:",
        f"  allocation_fraction: {config.budget.allocation_fraction}",
        f"  reserve_floor_percent: {config.budget.reserve_floor_percent}",
        f"  default_task_reservation_percent: {config.budget.default_task_reservation_percent}",
        f"  reservation_ttl_minutes: {config.budget.reservation_ttl_minutes}",
        "",
        "Workers:",
        *[
            f"  {provider}: model={worker.model}, budget_window={worker.budget_window}"
            for provider, worker in config.workers.by_provider.items()
        ],
        "",
        "Allowed work:",
        *[f"  - {item}" for item in config.guardrails.allowed_work],
        "",
        "Blocked paths:",
        *[f"  - {item}" for item in config.guardrails.blocked_paths],
        "",
        "Repos:",
    ]
    if config.repos:
        lines.extend(
            f"  - {repo.name}: {repo.path} ({'enabled' if repo.enabled else 'disabled'}, priority {repo.priority})"
            for repo in config.repos
        )
    else:
        lines.append("  (none configured)")

    lines.extend(
        [
            "",
            "Context imports:",
            *[f"  - {item}" for item in config.context.markdown],
            "",
            "Skill imports:",
            *[f"  - {item}" for item in config.context.skills],
        ]
    )
    return "\n".join(lines)


def _parse_workers(raw_workers: object) -> dict[str, WorkerConfig]:
    if not isinstance(raw_workers, dict):
        return {}

    workers: dict[str, WorkerConfig] = {}
    for provider, raw_worker in raw_workers.items():
        if not isinstance(raw_worker, dict):
            continue
        workers[str(provider)] = WorkerConfig(
            provider=str(provider),
            model=str(raw_worker.get("model", "")),
            budget_window=str(raw_worker.get("budget_window", "")),
        )
    return workers


def _parse_repos(raw_repos: object) -> list[RepoConfig]:
    repos: list[RepoConfig] = []
    if not isinstance(raw_repos, list):
        return repos

    for raw_repo in raw_repos:
        if not isinstance(raw_repo, dict):
            continue
        path = Path(str(raw_repo.get("path", ""))).expanduser()
        name = str(raw_repo.get("name") or path.name or "repo")
        commands = raw_repo.get("commands", {})
        if not isinstance(commands, dict):
            commands = {}
        repos.append(
            RepoConfig(
                name=name,
                path=path,
                enabled=bool(raw_repo.get("enabled", True)),
                priority=int(raw_repo.get("priority", 50)),
                test_command=str(commands.get("test", "")),
                lint_command=str(commands.get("lint", "")),
                typecheck_command=str(commands.get("typecheck", "")),
                format_check_command=str(commands.get("format_check", "")),
            )
        )
    return repos
