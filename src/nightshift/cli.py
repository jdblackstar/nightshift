from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nightshift.config import default_config_path, describe_config
from nightshift.errors import NightshiftError
from nightshift.context import render_context
from nightshift.doctor import doctor_passed, format_doctor_checks, run_doctor
from nightshift.init import init_global, init_repo_hints
from nightshift.repos import add_repo, list_repos, remove_repo, set_repo_enabled
from nightshift.tui import run_tui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nightshift",
        description="Plan and run explicit repo chores as disposable draft PRs.",
        epilog=(
            "Common commands:\n"
            "  nightshift init\n"
            "  nightshift repos add .\n"
            "  nightshift doctor\n"
            "  nightshift config view"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo",
        dest="repo_path",
        default=".",
        help="Repository path for interactive commands. Defaults to the current directory.",
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize global Nightshift configuration.",
        description="Create the operator-owned global config file used by scheduled Nightshift runs.",
        epilog="Example:\n  nightshift init\n  nightshift init --config /tmp/nightshift.toml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init_parser.add_argument(
        "--config",
        default=None,
        help="Config path to initialize. Defaults to ~/.nightshift/config.toml.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing Nightshift scaffold files.",
    )

    repo_parser = subparsers.add_parser(
        "repo",
        help="Manage optional repo-local Nightshift hints.",
        description="Manage optional files inside a repository that tell agents how to hand chores to Nightshift.",
        epilog="Example:\n  nightshift repo init\n  nightshift repo init /Users/josh/code/app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repo_subparsers = repo_parser.add_subparsers(dest="repo_command", required=True)
    repo_init_parser = repo_subparsers.add_parser(
        "init",
        help="Create optional .nightshift handoff context files in a repository.",
        description="Create .nightshift/context.md and a handoff skill in a repository.",
        epilog="Example:\n  nightshift repo init\n  nightshift repo init /Users/josh/code/app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repo_init_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path. Defaults to the current directory.",
    )
    repo_init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing repo hint files.",
    )

    repos_parser = subparsers.add_parser(
        "repos",
        help="Manage repositories in the global Nightshift config.",
        description="Add, list, remove, enable, or disable repositories in ~/.nightshift/config.toml.",
        epilog=(
            "Examples:\n"
            "  nightshift repos add .\n"
            "  nightshift repos list\n"
            "  nightshift repos disable app\n"
            "  nightshift repos remove /Users/josh/code/app"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repos_subparsers = repos_parser.add_subparsers(dest="repos_command", required=True)
    repos_add_parser = repos_subparsers.add_parser(
        "add",
        help="Add a repository to global Nightshift config.",
        description="Add a local repository path to the global config. Creates the config first if needed.",
        epilog="Example:\n  nightshift repos add .\n  nightshift repos add /Users/josh/code/app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repos_add_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path. Defaults to current directory.",
    )
    repos_add_parser.add_argument(
        "--config",
        default=None,
        help="Config path. Defaults to ~/.nightshift/config.toml.",
    )
    repos_list_parser = repos_subparsers.add_parser(
        "list",
        help="List configured repositories.",
        description="Print configured repositories as: name, status, path.",
        epilog="Example:\n  nightshift repos list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repos_list_parser.add_argument(
        "--config",
        default=None,
        help="Config path. Defaults to ~/.nightshift/config.toml.",
    )
    repos_remove_parser = repos_subparsers.add_parser(
        "remove",
        help="Remove a configured repository.",
        description="Remove a repository by configured name or path.",
        epilog="Example:\n  nightshift repos remove nightshift",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repos_remove_parser.add_argument("repo", help="Configured repo name or path.")
    repos_remove_parser.add_argument(
        "--config",
        default=None,
        help="Config path. Defaults to ~/.nightshift/config.toml.",
    )
    repos_enable_parser = repos_subparsers.add_parser(
        "enable",
        help="Enable a configured repository.",
        description="Allow Nightshift to consider a configured repository during planning.",
        epilog="Example:\n  nightshift repos enable nightshift",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repos_enable_parser.add_argument("repo", help="Configured repo name or path.")
    repos_enable_parser.add_argument(
        "--config",
        default=None,
        help="Config path. Defaults to ~/.nightshift/config.toml.",
    )
    repos_disable_parser = repos_subparsers.add_parser(
        "disable",
        help="Disable a configured repository.",
        description="Keep a repository in config but exclude it from planning.",
        epilog="Example:\n  nightshift repos disable nightshift",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repos_disable_parser.add_argument("repo", help="Configured repo name or path.")
    repos_disable_parser.add_argument(
        "--config",
        default=None,
        help="Config path. Defaults to ~/.nightshift/config.toml.",
    )

    context_parser = subparsers.add_parser(
        "context",
        help="Render imported Markdown and skills for an agent working in a repository.",
        description="Render the global context import list against a repository path for a bounded agent task.",
        epilog="Example:\n  nightshift context .\n  nightshift context /Users/josh/code/app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    context_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path. Defaults to the current directory.",
    )

    config_parser = subparsers.add_parser(
        "config",
        help="Manage Nightshift configuration.",
        description="Inspect Nightshift's global configuration.",
        epilog="Example:\n  nightshift config view",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", required=True
    )
    config_view_parser = config_subparsers.add_parser(
        "view",
        help="View global Nightshift configuration.",
        description="Print the effective global Nightshift configuration in a human-readable form.",
        epilog="Example:\n  nightshift config view\n  nightshift config view --config /tmp/nightshift.toml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    config_view_parser.add_argument(
        "--config",
        default=None,
        help="Config path. Defaults to ~/.nightshift/config.toml.",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check local Nightshift setup.",
        description="Check config, repos, required CLIs, GitHub auth, and workdir access.",
        epilog=(
            "Examples:\n"
            "  nightshift doctor\n"
            "  nightshift doctor --skip-auth\n"
            "  nightshift doctor --fail-on-unknown-providers\n"
            "  nightshift doctor --config /tmp/nightshift.toml"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    doctor_parser.add_argument(
        "--config",
        default=None,
        help="Config path. Defaults to ~/.nightshift/config.toml.",
    )
    doctor_parser.add_argument(
        "--skip-auth",
        action="store_true",
        help="Skip gh auth status. Useful in CI or offline checks.",
    )
    doctor_parser.add_argument(
        "--fail-on-unknown-providers",
        action="store_true",
        help=(
            "Treat enabled provider names outside the built-in set as failures. "
            "Default is warn-only; use this in CI or automation so typos exit non-zero."
        ),
    )

    tui_parser = subparsers.add_parser(
        "dashboard",
        aliases=["tui"],
        help="Open the Nightshift Textual dashboard for review/monitoring.",
        description="Open the Textual dashboard. Use one-off commands for setup and automation.",
        epilog="Example:\n  nightshift dashboard\n  nightshift dashboard /Users/josh/code/app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    tui_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Repository path. Defaults to --repo or the current directory.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command is None:
            parser.print_help()
            return 0

        if args.command == "init":
            result = init_global(
                Path(args.config) if args.config else None,
                force=args.force,
            )
            for created in result.created:
                print(f"created {created}")
            for skipped in result.skipped:
                print(f"exists  {skipped}")
            return 0

        if args.command == "repo":
            if args.repo_command == "init":
                result = init_repo_hints(Path(args.path), force=args.force)
                for created in result.created:
                    print(f"created {created}")
                for skipped in result.skipped:
                    print(f"exists  {skipped}")
                return 0

        if args.command == "repos":
            cfg = Path(args.config) if args.config else None
            if args.repos_command == "add":
                change = add_repo(Path(args.path), cfg)
                preposition = "in" if change.action == "exists" else "to"
                plain = f"{change.action} {change.repo.name} {preposition} {change.config_path}"
                rich = (
                    f"[green]{change.action}[/green] "
                    f"{_escape_rich_text(change.repo.name)} {preposition} "
                    f"{_escape_rich_text(str(change.config_path))}"
                )
                _print_status(rich, plain_line=plain)
                return 0
            if args.repos_command == "list":
                repos = list_repos(cfg)
                if not repos:
                    print("no repos")
                    return 0
                for repo in repos:
                    status = "enabled" if repo.enabled else "disabled"
                    print(f"{repo.name}\t{status}\t{repo.path}")
                return 0
            if args.repos_command == "remove":
                change = remove_repo(args.repo, cfg)
                plain = f"removed {change.repo.name} from {change.config_path}"
                rich = (
                    f"[green]removed[/green] {_escape_rich_text(change.repo.name)} "
                    f"from {_escape_rich_text(str(change.config_path))}"
                )
                _print_status(rich, plain_line=plain)
                return 0
            if args.repos_command == "enable":
                change = set_repo_enabled(args.repo, True, cfg)
                plain = f"enabled {change.repo.name}"
                rich = f"[green]enabled[/green] {_escape_rich_text(change.repo.name)}"
                _print_status(rich, plain_line=plain)
                return 0
            if args.repos_command == "disable":
                change = set_repo_enabled(args.repo, False, cfg)
                plain = f"disabled {change.repo.name}"
                rich = f"[green]disabled[/green] {_escape_rich_text(change.repo.name)}"
                _print_status(rich, plain_line=plain)
                return 0

        if args.command == "context":
            print(render_context(Path(args.path)))
            return 0

        if args.command == "config":
            if args.config_command == "view":
                print(describe_config(Path(args.config) if args.config else None))
                return 0

        if args.command == "doctor":
            checks = run_doctor(
                Path(args.config) if args.config else default_config_path(),
                check_auth=not args.skip_auth,
                fail_on_unknown_providers=args.fail_on_unknown_providers,
            )
            print(format_doctor_checks(checks))
            return 0 if doctor_passed(checks) else 1

        if args.command in {"dashboard", "tui"}:
            return run_tui(Path(args.path or args.repo_path))

    except (
        NightshiftError,
        FileNotFoundError,
        PermissionError,
        ValueError,
    ) as exc:
        print(f"nightshift: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


def _escape_rich_text(text: str) -> str:
    """Return ``text`` safe to embed in Rich markup strings."""
    try:
        from rich.markup import escape
    except ModuleNotFoundError:
        return text
    return escape(text)


def _print_status(rich_line: str, *, plain_line: str | None = None) -> None:
    try:
        from rich.console import Console
    except ModuleNotFoundError:
        print(
            plain_line
            if plain_line is not None
            else rich_line.replace("[green]", "").replace("[/green]", "")
        )
        return
    Console(highlight=False, width=10_000, soft_wrap=True).print(rich_line)


if __name__ == "__main__":
    raise SystemExit(main())
