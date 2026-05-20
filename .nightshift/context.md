# Nightshift Context

Nightshift is allowed to pick up explicit chores in this repository while the
maintainer is away.

Use Nightshift for:

- failing tests, type checks, lint, and formatting
- comments tagged `TODO(nightshift)` or `FIXME(nightshift)`
- GitHub issues labeled `nightshift`
- documentation updates tied to existing behavior

Do not use Nightshift for:

- inventing features
- broad refactors
- product or design decisions
- auth, billing, secrets, infrastructure, migrations, or deployment changes
  unless this repo config explicitly allows them

Preferred handoff comments:

```py
# TODO(nightshift): add regression coverage for empty payload handling
# FIXME(nightshift): handle null profile returned by the API
```

Each task completed by Nightshift should become one draft PR with a narrow scope
and a verification section.
