# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Nightshift is a Python CLI/TUI tool (Textual-based) that scans repos for actionable chores and creates draft PRs. The project uses `uv` for package management with a `uv.lock` lockfile.

### Key commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Run app | `.venv/bin/nightshift` |
| Lint | `.venv/bin/ruff check src/ tests/` |
| Format | `.venv/bin/ruff format src/ tests/` |
| Test | `.venv/bin/pytest tests/ -v` |

### Caveats

- **`uv` must be on PATH**: The VM update script installs `uv` to `~/.local/bin`. Ensure `PATH` includes `$HOME/.local/bin` (already configured in `~/.bashrc`).
- **No async test plugin**: The project does not include `pytest-asyncio`. Textual's `run_test()` async context manager cannot be used in tests without adding it as a dev dependency first.
- **Layout**: Source code lives in `src/nightshift/` and tests in `tests/`, per `pyproject.toml` `[tool.pytest.ini_options]` config.
- **Entry point**: The CLI entry point is `nightshift.cli:main`, which launches a Textual TUI app. It requires a terminal (TTY) to render; use `tmux` sessions for background runs.
