# Nightshift

Nightshift puts unused AI subscription usage to work while you sleep.

It is not here to invent features. It looks for the following in configured repos:

- failing tests, type checks, lint, or formatting
- `TODO(nightshift)` or `FIXME(nightshift)` comments
- GitHub issues labeled `nightshift:*`
- review comments or docs tasks explicitly tagged for Nightshift

The intended output unit is one draft pull request per task.

## First Commands

v0.1 is intentionally small: it configures Nightshift, reads provider usage,
checks local readiness, and prints deterministic dry-run plans. It does not yet
run the full overnight worker loop end to end.

Install the local checkout as an editable command:

```bash
uv tool install --editable .
nightshift --help
```

During development, run tests from the repo:

```bash
uv run pytest
```

```bash
nightshift init
nightshift repos add .
nightshift doctor
nightshift repos list
nightshift providers usage
nightshift plan
nightshift workers command codex --repo .
nightshift reservations list
nightshift config view
nightshift repo init
nightshift context
nightshift dashboard
```

`nightshift init` creates the operator-owned global config:

- `~/.nightshift/config.toml`

`nightshift repo init` can optionally create repo-local agent handoff files:

- `.nightshift/context.md`
- `.nightshift/skills/nightshift-handoff/SKILL.md`

`nightshift context` renders the imported Markdown files and skill files that
should be included when an agent works on the repository.

Repository management is intentionally direct and quiet:

```bash
nightshift repos add .
nightshift repos remove nightshift
nightshift repos enable nightshift
nightshift repos disable nightshift
```

Provider usage is read through `codexbar`:

```bash
nightshift providers usage
nightshift providers usage cursor
nightshift providers usage --timeout 5
nightshift providers usage --source cache
nightshift providers usage --source live
```

By default, Nightshift uses `--source auto`: it reads CodexBar's latest
widget/history cache first, then falls back to live `codexbar` probes for
providers without cached data.

For rolling windows with a reset time and window length, usage output includes
reserve when the account is behind pace:

```text
codex	weekly	86% left	May 7, 2026 at 13:32	43% reserve
```

`nightshift doctor` checks the local machine before an overnight run:

```bash
nightshift doctor
nightshift doctor --skip-auth
```

It verifies the global config, configured repos, required local CLIs, CodexBar
cache availability, GitHub auth, and workdir access.

`nightshift plan` is a dry run. It reads the configured provider order, local
usage reserve, active budget reservations, and enabled repos, then prints what
Nightshift would run:

```bash
nightshift plan
nightshift plan --source auto
```

The default source is `cache` so planning does not stall on live provider probes.

Worker command defaults are configured per provider. Codex and Claude default to
their subscription weekly windows. Cursor runs are pinned to Composer 2 and
budgeted against Cursor's Auto bucket:

```toml
[workers.codex]
model = ""
budget_window = "weekly"

[workers.claude]
model = ""
budget_window = "weekly"

[workers.cursor]
model = "composer-2"
budget_window = "Auto"
```

Scheduler and budget defaults are conservative:

```toml
[scheduler]
strategy = "priority"
provider_order = ["codex", "claude", "cursor"]
max_workers = 2

[budget]
allocation_fraction = 0.5
reserve_floor_percent = 5
default_task_reservation_percent = 5
reservation_ttl_minutes = 90
```

Nightshift uses local budget reservations to prevent multiple workers from
starting against the same stale provider snapshot:

```bash
nightshift reservations list
nightshift reservations add codex weekly nightshift
nightshift reservations release rsv_...
```

Worker commands can be inspected without launching an agent. The dry run prints
both the process cwd and argv; launch code should run the command from that cwd.

```bash
nightshift workers command codex --repo .
nightshift workers command claude --repo .
nightshift workers command cursor --repo . --prompt "fix failing tests"
```

Use one-off commands for setup, automation, and agent handoff data. Use the
Textual dashboard only for stateful review and monitoring.
