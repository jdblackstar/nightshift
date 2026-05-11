# Nightshift

Nightshift is a tool to put your unused AI subscription usage to work while you sleep.

It is not here to invent features. It looks for the following in configured repos:

- failing tests, type checks, lint, or formatting
- `TODO(nightshift)` or `FIXME(nightshift)` comments
- GitHub issues labeled `nightshift:*`
- review comments or docs tasks explicitly tagged for Nightshift

The intended output unit is one draft pull request per task.

## First Commands

Nightshift starts with configuration, repository registration, local readiness
checks, and repo-local handoff context. It does not run overnight work yet.

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

`nightshift context` renders the imported Markdown files and skill files that should be included when an agent works on the repository.

Repository management is intentionally direct and quiet:

```bash
nightshift repos add .
nightshift repos remove nightshift
nightshift repos enable nightshift
nightshift repos disable nightshift
```

`nightshift doctor` checks the local machine before an overnight run:

```bash
nightshift doctor
nightshift doctor --skip-auth
```

It verifies the global config, configured repos, required local CLIs, GitHub
auth, and workdir access.

Use one-off commands for setup, automation, and agent handoff data. Use the Textual dashboard only for stateful review and monitoring. The command structure follows the same practical shape as tools like Prime Intellect's CLI: scriptable verbs for automation, grouped config commands, and an interactive terminal surface where it earns its keep.
