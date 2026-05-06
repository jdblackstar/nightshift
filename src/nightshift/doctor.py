from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Literal, Sequence
from uuid import uuid4

from nightshift.config import load_config


Status = Literal["ok", "warn", "fail"]
OK: Status = "ok"
WARN: Status = "warn"
FAIL: Status = "fail"
REQUIRED_PROVIDER_COMMANDS = {
    "codex": "codex",
    "claude": "claude",
    "cursor": "cursor-agent",
}

KNOWN_PROVIDER_NAMES = frozenset(REQUIRED_PROVIDER_COMMANDS.keys())


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: Status
    detail: str


def run_doctor(
    config_path: Path,
    *,
    check_auth: bool = True,
    fail_on_unknown_providers: bool = False,
) -> tuple[DoctorCheck, ...]:
    """Health checks for config, repos, CLIs, workdir, and optional gh auth."""
    config_file = config_path.expanduser().resolve()
    if not config_file.exists():
        return (
            DoctorCheck(
                "config", FAIL, f"{config_file} missing; run `nightshift init`"
            ),
        )

    config = load_config(config_file)
    checks = [DoctorCheck("config", OK, str(config_file))]
    checks.append(
        DoctorCheck(
            "repos",
            OK if config.repos else WARN,
            f"{len(config.repos)} configured"
            if config.repos
            else "no repos configured",
        )
    )
    for repo in config.repos:
        exists = repo.path.exists()
        status = "enabled" if repo.enabled else "disabled"
        checks.append(
            DoctorCheck(
                f"repo {repo.name}",
                OK if exists else FAIL,
                f"{status}: {repo.path}" if exists else f"missing: {repo.path}",
            )
        )
    expected_providers = ", ".join(sorted(REQUIRED_PROVIDER_COMMANDS))
    for provider in config.providers.enabled:
        if provider not in KNOWN_PROVIDER_NAMES:
            unknown_status = FAIL if fail_on_unknown_providers else WARN
            checks.append(
                DoctorCheck(
                    f"provider {provider}",
                    unknown_status,
                    "unknown provider name; expected one of: "
                    f"{expected_providers}",
                )
            )
    commands = ["codexbar", "gh"]
    for provider in config.providers.enabled:
        mapped = REQUIRED_PROVIDER_COMMANDS.get(provider)
        if mapped is None:
            continue
        if mapped not in commands:
            commands.append(mapped)
    for command in commands:
        path = shutil.which(command)
        checks.append(
            DoctorCheck(
                f"cli {command}", OK if path else FAIL, path or "not found on PATH"
            )
        )
    checks.append(_workdir_check(config.workdir))
    if check_auth:
        checks.append(_github_auth_check())
    return tuple(checks)


def format_doctor_checks(checks: Sequence[DoctorCheck]) -> str:
    if not checks:
        return "no checks"
    mark = {"ok": "[ok]", "warn": "[warn]", "fail": "[fail]"}
    return "\n".join(
        f"{mark[check.status]} {check.name}: {check.detail}" for check in checks
    )


def doctor_passed(checks: Sequence[DoctorCheck]) -> bool:
    return all(check.status != FAIL for check in checks)


def _workdir_check(workdir: Path) -> DoctorCheck:
    try:
        workdir.mkdir(parents=True, exist_ok=True)
        probe = workdir / f".nightshift-doctor-{uuid4().hex}"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return DoctorCheck("workdir", FAIL, f"{workdir}: {exc}")
    return DoctorCheck("workdir", OK, str(workdir))


def _github_auth_check() -> DoctorCheck:
    if shutil.which("gh") is None:
        return DoctorCheck("github auth", FAIL, "gh not found on PATH")
    try:
        result = _run(["gh", "auth", "status"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck("github auth", FAIL, str(exc))
    if result.returncode == 0:
        return DoctorCheck("github auth", OK, "gh auth status passed")
    message = (result.stderr or result.stdout or "gh auth status failed").strip()
    return DoctorCheck("github auth", FAIL, message)


def _run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
