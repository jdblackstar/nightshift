from __future__ import annotations

from pathlib import Path

from nightshift.config import NightshiftConfig, load_config


def run_tui(repo_path: Path) -> int:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal
    from textual.widgets import Footer, Header, Static

    class NightshiftApp(App[None]):
        CSS = """
        Screen {
            background: $surface;
        }

        #page {
            height: 1fr;
            padding: 1 2;
        }

        .row {
            height: auto;
        }

        .panel {
            border: round $primary;
            padding: 1 2;
            margin: 0 1 1 0;
            width: 1fr;
            height: auto;
        }

        .muted {
            color: $text-muted;
        }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
        ]

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.repo_path = path.expanduser().resolve()
            try:
                self._config: NightshiftConfig | None = load_config()
            except FileNotFoundError:
                self._config = None

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Container(id="page"):
                yield Static("Nightshift", classes="muted")
                yield self._summary_panel()
                with Horizontal(classes="row"):
                    yield self._allowed_panel()
                    yield self._blocked_panel()
                with Horizontal(classes="row"):
                    yield self._commands_panel()
                    yield self._context_panel()
                yield Static(
                    "Default mode: chores only, one draft PR per task, no feature invention.",
                    classes="muted",
                )
            yield Footer()

        def _summary_panel(self) -> Static:
            cfg = self._config
            if cfg is None:
                body = (
                    f"[b]Working directory[/b]\n{self.repo_path}\n\n"
                    "[b]Status[/b]\nNot initialized\n\n"
                    "Run `nightshift init` to create ~/.nightshift/config.toml."
                )
            else:
                body = (
                    f"[b]Config[/b]\n{cfg.config_path}\n\n"
                    f"[b]Schedule[/b]\n{cfg.schedule}\n\n"
                    "[b]Workflow[/b]\n"
                    "Explicit signal -> isolated worktree -> checks -> draft PR"
                )
            return Static(body, classes="panel")

        def _allowed_panel(self) -> Static:
            cfg = self._config
            items = (
                "\n".join(f"- {item}" for item in cfg.guardrails.allowed_work)
                if cfg
                else "No config loaded."
            )
            return Static(f"[b]Allowed Work[/b]\n{items}", classes="panel")

        def _blocked_panel(self) -> Static:
            cfg = self._config
            items = (
                "\n".join(f"- {item}" for item in cfg.guardrails.blocked_paths)
                if cfg
                else "No config loaded."
            )
            return Static(f"[b]Blocked Paths[/b]\n{items}", classes="panel")

        def _commands_panel(self) -> Static:
            cfg = self._config
            if not cfg:
                items = "No config loaded."
            elif cfg.repos:
                items = "\n".join(
                    f"{repo.name}: {repo.path} ({'enabled' if repo.enabled else 'disabled'})"
                    for repo in cfg.repos
                )
            else:
                items = "No repositories configured."
            return Static(f"[b]Repos[/b]\n{items}", classes="panel")

        def _context_panel(self) -> Static:
            cfg = self._config
            if not cfg:
                items = "No config loaded."
            else:
                imports = "\n".join(f"- {item}" for item in cfg.context.markdown)
                skills = "\n".join(f"- {item}" for item in cfg.context.skills)
                items = f"[b]Markdown[/b]\n{imports}\n\n[b]Skills[/b]\n{skills}"
            return Static(f"[b]Agent Context[/b]\n{items}", classes="panel")

    NightshiftApp(repo_path).run()
    return 0
