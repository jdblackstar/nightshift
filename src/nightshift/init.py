from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nightshift.config import default_config_path


DEFAULT_GLOBAL_CONFIG = """# Nightshift global configuration.
# This file is operator-owned and normally lives at ~/.nightshift/config.toml.

[runtime]
schedule = "00:00-05:00"
workdir = "~/.nightshift/work"

[github]
# v1 setup can use `gh` for interactive auth. Overnight runs should eventually
# use a GitHub App installation token instead of a personal token.
auth = "gh"

[providers]
usage_source = "codexbar"
enabled = ["codex", "claude", "cursor"]

[scheduler]
strategy = "priority"
provider_order = ["codex", "claude", "cursor"]
max_workers = 2

[budget]
allocation_fraction = 0.5
reserve_floor_percent = 5
default_task_reservation_percent = 5
reservation_ttl_minutes = 90

[workers.codex]
model = ""
budget_window = "weekly"

[workers.claude]
model = ""
budget_window = "weekly"

[workers.cursor]
# Cursor should use the Auto bucket, not API. Cursor Agent's CLI model id for
# Composer 2 is `composer-2`, passed as `--model composer-2`.
model = "composer-2"
budget_window = "Auto"

[pull_requests]
enabled = true
draft = true
base_branch = "main"
max_open_per_repo = 1
delete_branch_on_close = true

[guardrails]
allowed_work = [
  "failing_tests",
  "type_errors",
  "lint_errors",
  "formatting",
  "tagged_todos",
  "tagged_fixmes",
  "nightshift_labeled_issues",
  "docs_for_existing_behavior",
]
blocked_paths = [
  ".env",
  ".env.*",
  "secrets/",
  "infra/",
  "migrations/",
  "billing/",
]

[signals]
comment_tags = ["TODO(nightshift)", "FIXME(nightshift)", "nightshift:"]
github_labels = ["nightshift", "nightshift:test", "nightshift:lint", "nightshift:docs", "nightshift:deps"]

[context]
# These paths are resolved relative to each configured repository.
imports = [
  ".nightshift/context.md",
  "README.md",
]
skills = [
  ".nightshift/skills/nightshift-handoff/SKILL.md",
]

# Add repositories here or through a future `nightshift repos add` command.
# [[repos]]
# name = "example"
# path = "/Users/josh/code/example"
# enabled = true
# priority = 50
#
# [repos.commands]
# test = "npm test"
# lint = "npm run lint"
# typecheck = "npm run typecheck"
# format_check = "npm run format:check"
"""


DEFAULT_CONTEXT = """# Nightshift Context

Nightshift is allowed to pick up explicit chores in this repository while the maintainer is away.

Use Nightshift for:

- failing tests, type checks, lint, and formatting
- comments tagged `TODO(nightshift)` or `FIXME(nightshift)`
- GitHub issues labeled `nightshift`
- documentation updates tied to existing behavior

Do not use Nightshift for:

- inventing features
- broad refactors
- product or design decisions
- auth, billing, secrets, infrastructure, migrations, or deployment changes unless the global Nightshift config explicitly allows them

Preferred handoff comments:

```ts
// TODO(nightshift): add regression coverage for empty payload handling
// FIXME(nightshift): handle null profile returned by the API
```

Each completed task should become one draft PR with a narrow scope and a verification section.
"""


DEFAULT_SKILL = """# Nightshift Handoff

Use this skill when you are an agent working in this repository and you find cleanup work that should be deferred to Nightshift instead of handled immediately.

## Purpose

Nightshift is an async chore runner. It can take over explicit, bounded cleanup tasks and turn them into disposable draft PRs.

## Good Handoffs

Leave a precise code comment near the work:

```ts
// TODO(nightshift): add tests for the empty invoice payload path
// FIXME(nightshift): remove this fallback after the parser accepts v2 payloads
```

Or create/label a GitHub issue with `nightshift`.

## Boundaries

Only hand off chores. Do not ask Nightshift to invent features, redesign UI, make product calls, or perform broad refactors.

Useful Nightshift tasks include:

- adding missing tests for existing behavior
- fixing type/lint/formatting fallout
- updating docs for already-merged behavior
- addressing small, explicit follow-ups

## PR Contract

Nightshift should produce one draft PR per task. The PR should link to the source signal, explain changes, list verification commands, and remain easy to close.
"""


@dataclass(frozen=True)
class InitResult:
    created: tuple[Path, ...]
    skipped: tuple[Path, ...]


def init_global(config_path: Path | None = None, *, force: bool = False) -> InitResult:
    path = (config_path or default_config_path()).expanduser().resolve()
    return _write_files({path: DEFAULT_GLOBAL_CONFIG}, force=force)


def init_repo_hints(repo_path: Path, *, force: bool = False) -> InitResult:
    root = repo_path.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return _write_files(
        {
            root / ".nightshift" / "context.md": DEFAULT_CONTEXT,
            root
            / ".nightshift"
            / "skills"
            / "nightshift-handoff"
            / "SKILL.md": DEFAULT_SKILL,
        },
        force=force,
    )


def _write_files(files: dict[Path, str], *, force: bool) -> InitResult:
    created: list[Path] = []
    skipped: list[Path] = []

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            skipped.append(path)
            continue
        path.write_text(content, encoding="utf-8")
        created.append(path)

    return InitResult(created=tuple(created), skipped=tuple(skipped))
