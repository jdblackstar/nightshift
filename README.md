# Nightshift

Nightshift is a tool to put your unused AI subscription usage to work while you sleep.

It is not here to invent features. It looks for the following in configured repos:

- failing tests, type checks, lint, or formatting
- `TODO(nightshift)` or `FIXME(nightshift)` comments
- GitHub issues labeled `nightshift:*`
- review comments or docs tasks explicitly tagged for Nightshift

The intended output unit is one draft pull request per task.
