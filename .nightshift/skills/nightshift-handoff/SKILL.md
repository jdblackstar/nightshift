# Nightshift Handoff

Use this skill when you are an agent working in this repository and you find
cleanup work that should be deferred to Nightshift instead of handled
immediately.

## Purpose

Nightshift is an async chore runner. It can take over explicit, bounded cleanup
tasks and turn them into easy-to-close draft PRs.

## Good Handoffs

Leave a precise code comment near the work:

```py
# TODO(nightshift): add tests for the empty invoice payload path
# FIXME(nightshift): remove this fallback after the parser accepts v2 payloads
```

Or create/label a GitHub issue with `nightshift`.

## Boundaries

Only hand off chores. Do not ask Nightshift to invent features, redesign UI,
make product calls, or perform broad refactors.

Useful Nightshift tasks include:

- adding missing tests for existing behavior
- fixing type/lint/formatting fallout
- updating docs for already-merged behavior
- addressing small, explicit follow-ups

## PR Contract

Nightshift should produce one draft PR per task it completes. The PR should link
to the source signal, explain changes, list verification commands, and remain
easy to close.
