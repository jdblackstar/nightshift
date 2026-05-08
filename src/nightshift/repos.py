from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from nightshift.config import RepoConfig, default_config_path, load_config
from nightshift.init import init_global


@dataclass(frozen=True)
class RepoChange:
    action: str
    repo: RepoConfig
    config_path: Path


def add_repo(repo_path: Path, config_path: Path | None = None) -> RepoChange:
    path = repo_path.expanduser().resolve()
    config_file = _ensure_config(config_path)
    config = load_config(config_file)
    name = _repo_name(path)

    for repo in config.repos:
        if repo.path.expanduser().resolve() == path:
            return RepoChange("exists", repo, config_file)

    repo = RepoConfig(
        name=name,
        path=path,
        enabled=True,
        priority=50,
        test_command=_detect_test_command(path),
        lint_command=_detect_lint_command(path),
        typecheck_command=_detect_typecheck_command(path),
        format_check_command=_detect_format_check_command(path),
    )
    _append_repo(config_file, repo)
    return RepoChange("added", repo, config_file)


def list_repos(config_path: Path | None = None) -> tuple[RepoConfig, ...]:
    return load_config(config_path).repos


def remove_repo(name_or_path: str, config_path: Path | None = None) -> RepoChange:
    config_file = _resolve_config(config_path)
    config = load_config(config_file)
    repo = _find_repo(config.repos, name_or_path)
    remaining = [item for item in config.repos if item != repo]
    _rewrite_repos(config_file, remaining)
    return RepoChange("removed", repo, config_file)


def set_repo_enabled(
    name_or_path: str,
    enabled: bool,
    config_path: Path | None = None,
) -> RepoChange:
    config_file = _resolve_config(config_path)
    config = load_config(config_file)
    repo = _find_repo(config.repos, name_or_path)
    updated = RepoConfig(
        name=repo.name,
        path=repo.path,
        enabled=enabled,
        priority=repo.priority,
        test_command=repo.test_command,
        lint_command=repo.lint_command,
        typecheck_command=repo.typecheck_command,
        format_check_command=repo.format_check_command,
    )
    repos = [updated if item == repo else item for item in config.repos]
    _rewrite_repos(config_file, repos)
    return RepoChange("enabled" if enabled else "disabled", updated, config_file)


def _ensure_config(config_path: Path | None) -> Path:
    config_file = _resolve_config(config_path)
    if not config_file.exists():
        init_global(config_file)
    return config_file


def _resolve_config(config_path: Path | None) -> Path:
    return (config_path or default_config_path()).expanduser().resolve()


def _find_repo(repos: tuple[RepoConfig, ...], name_or_path: str) -> RepoConfig:
    requested = Path(name_or_path).expanduser()
    requested_resolved = requested.resolve() if requested.exists() else None
    for repo in repos:
        if repo.name == name_or_path:
            return repo
        if (
            requested_resolved is not None
            and repo.path.expanduser().resolve() == requested_resolved
        ):
            return repo
        if str(repo.path) == name_or_path:
            return repo
    raise ValueError(f"repo not found: {name_or_path}")


def _repo_name(path: Path) -> str:
    remote = _git_remote(path)
    if remote:
        return remote.rsplit("/", 1)[-1].removesuffix(".git")
    return path.name


def _git_remote(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    remote = result.stdout.strip()
    if remote.startswith("git@github.com:"):
        return remote.removeprefix("git@github.com:")
    if remote.startswith("https://github.com/"):
        return remote.removeprefix("https://github.com/")
    return remote or None


def _detect_command_for_repo(
    path: Path,
    *,
    pyproject_command: str | None,
    npm_script: str,
    cargo_command: str | None,
) -> str:
    """Pick a command using the same ecosystem order as test detection."""
    if (path / "pyproject.toml").exists() and pyproject_command:
        return pyproject_command
    if (path / "package.json").exists():
        return f"npm run {npm_script}"
    if (path / "Cargo.toml").exists() and cargo_command:
        return cargo_command
    return ""


def _detect_test_command(path: Path) -> str:
    return _detect_command_for_repo(
        path,
        pyproject_command="uv run pytest",
        npm_script="test",
        cargo_command="cargo test",
    )


def _detect_lint_command(path: Path) -> str:
    return _detect_command_for_repo(
        path,
        pyproject_command="uv run ruff check .",
        npm_script="lint",
        cargo_command="cargo clippy",
    )


def _detect_typecheck_command(path: Path) -> str:
    return _detect_command_for_repo(
        path,
        pyproject_command=None,
        npm_script="typecheck",
        cargo_command="cargo check",
    )


def _detect_format_check_command(path: Path) -> str:
    return _detect_command_for_repo(
        path,
        pyproject_command="uv run ruff format --check .",
        npm_script="format:check",
        cargo_command="cargo fmt --check",
    )


def _append_repo(config_path: Path, repo: RepoConfig) -> None:
    existing = config_path.read_text(encoding="utf-8").rstrip()
    config_path.write_text(
        existing + "\n\n" + _render_repo(repo),
        encoding="utf-8",
    )


def _rewrite_repos(config_path: Path, repos: list[RepoConfig]) -> None:
    original = config_path.read_text(encoding="utf-8")
    head, tail = _split_repo_section(original)
    rendered_repos = "\n\n".join(_render_repo(repo).rstrip() for repo in repos)
    next_text = head.rstrip()
    if rendered_repos:
        next_text += "\n\n" + rendered_repos.rstrip()
    if tail.strip():
        next_text += "\n\n" + tail.lstrip()
    config_path.write_text(next_text.rstrip() + "\n", encoding="utf-8")


def _split_repo_section(text: str) -> tuple[str, str]:
    lines = text.splitlines(keepends=True)
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == "[[repos]]"),
        None,
    )
    if start is None:
        return text, ""

    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if (
            stripped.startswith("[")
            and stripped.endswith("]")
            and stripped
            not in {
                "[[repos]]",
                "[repos.commands]",
            }
        ):
            end = index
            break

    return "".join(lines[:start]), "".join(lines[end:])


def _render_repo(repo: RepoConfig) -> str:
    lines = [
        "[[repos]]",
        f'name = "{_escape(repo.name)}"',
        f'path = "{_escape(str(repo.path))}"',
        f"enabled = {_bool(repo.enabled)}",
        f"priority = {repo.priority}",
        "",
        "[repos.commands]",
        f'test = "{_escape(repo.test_command)}"',
        f'lint = "{_escape(repo.lint_command)}"',
        f'typecheck = "{_escape(repo.typecheck_command)}"',
        f'format_check = "{_escape(repo.format_check_command)}"',
    ]
    return "\n".join(lines) + "\n"


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
