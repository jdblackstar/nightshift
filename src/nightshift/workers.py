from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nightshift.config import NightshiftConfig, WorkerConfig
from nightshift.errors import NightshiftConfigError


@dataclass(frozen=True)
class WorkerInvocation:
    command: list[str]
    cwd: Path


def worker_invocation(
    provider: str, config: NightshiftConfig, workspace: Path, prompt: str
) -> WorkerInvocation:
    resolved_workspace = workspace.expanduser().resolve()
    return WorkerInvocation(
        command=worker_command(provider, config, resolved_workspace, prompt),
        cwd=resolved_workspace,
    )


def worker_command(
    provider: str, config: NightshiftConfig, workspace: Path, prompt: str
) -> list[str]:
    match provider:
        case "codex":
            return _codex_command(config.workers.get(provider), workspace, prompt)
        case "claude":
            return _claude_command(config.workers.get(provider), workspace, prompt)
        case "cursor":
            return _cursor_command(config.workers.get(provider), workspace, prompt)
        case _:
            raise NightshiftConfigError(f"unsupported worker provider: {provider}")


def worker_budget_window(provider: str, config: NightshiftConfig) -> str:
    return config.workers.get(provider).budget_window


def _codex_command(worker: WorkerConfig, workspace: Path, prompt: str) -> list[str]:
    command = [
        "codex",
        "exec",
        "--cd",
        str(workspace),
        "--sandbox",
        "workspace-write",
    ]
    if worker.model:
        command.extend(["--model", worker.model])
    command.append(prompt)
    return command


def _claude_command(worker: WorkerConfig, workspace: Path, prompt: str) -> list[str]:
    command = [
        "claude",
        "--print",
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "text",
        "--add-dir",
        str(workspace),
    ]
    if worker.model:
        command.extend(["--model", worker.model])
    command.append(prompt)
    return command


def _cursor_command(worker: WorkerConfig, workspace: Path, prompt: str) -> list[str]:
    command = [
        "cursor-agent",
        "--print",
        "--trust",
        "--workspace",
        str(workspace),
    ]
    if worker.model:
        command.extend(["--model", worker.model])
    command.append(prompt)
    return command
