"""Command-line interface for Nightshift."""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static


class NightshiftApp(App):
    """A TUI application for managing Nightshift tasks."""

    TITLE = "Nightshift"
    SUB_TITLE = "Put unused AI subscription usage to work"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Static(
            "Welcome to Nightshift!\n\n"
            "Nightshift scans your repos for actionable chores and creates draft PRs.\n\n"
            "Supported tasks:\n"
            "  • Failing tests, type checks, lint, or formatting\n"
            "  • TODO(nightshift) / FIXME(nightshift) comments\n"
            "  • GitHub issues labeled nightshift:*\n"
            "  • Review comments tagged for Nightshift\n\n"
            "Press [bold]q[/bold] to quit.",
        )
        yield Footer()


def main() -> None:
    """Entry point for the nightshift CLI."""
    app = NightshiftApp()
    app.run()


if __name__ == "__main__":
    main()
