# Provider Control Capabilities

Nightshift workers run through local provider CLIs. Steer commands are
provider-specific and should be modeled as capabilities, not assumed globally.

## Codex

Observed CLI surface:

- `codex exec [PROMPT]`
- `codex exec resume [SESSION_ID] [PROMPT]`
- `codex resume [SESSION_ID] [PROMPT]`
- `codex app-server` with `stdio://`, `unix://`, and `ws://` transports

Likely control options:

- Start a non-interactive task with `codex exec`.
- Send a later steer message with `codex exec resume <session-id> <message>` if
  Nightshift can capture/persist the session id.
- Investigate `codex app-server` as the best long-lived control channel before
  relying on TUI automation.

Initial capability estimate:

```text
start_task: yes
resume_with_message: likely
live_stdin_steering: unknown
structured_events: yes, via --json
recommended_v1: run bounded exec tasks; use resume for budget stop/pressure if session id is available
```

## Claude

Observed CLI surface:

- `claude -p/--print`
- `--input-format stream-json`
- `--output-format stream-json`
- `--include-partial-messages`
- `--resume`, `--continue`, `--session-id`
- `--max-budget-usd` for API-key print mode

Likely control options:

- Start a non-interactive task with `claude -p`.
- For live steering, use `--input-format stream-json --output-format stream-json`
  with a managed stdin stream.
- For follow-up steering, resume the saved session with `--resume <session-id>`
  or `--continue` if the session id is captured.

Initial capability estimate:

```text
start_task: yes
resume_with_message: yes
live_stdin_steering: likely via stream-json
structured_events: yes, via stream-json/json
recommended_v1: run print-mode bounded tasks; investigate stream-json for live budget pressure messages
```

## Cursor

Observed CLI surface:

- `cursor-agent [prompt]`
- `cursor-agent -p/--print`
- `--output-format text|json|stream-json`
- `--resume [chatId]`, `--continue`
- `cursor-agent create-chat`
- `cursor-agent resume`
- `--worktree`, `--workspace`, `--trust`, `--force`

Likely control options:

- Start a non-interactive task with `cursor-agent -p`.
- Create or resume chats with `create-chat` and `--resume`.
- No obvious documented live stdin message protocol from the help output.

Initial capability estimate:

```text
start_task: yes
resume_with_message: likely
live_stdin_steering: unknown
structured_events: yes, via --output-format stream-json
recommended_v1: treat as non-interactive or resumable; use process timeout/stop as fallback for budget pressure
```

## Nightshift Control Model

Nightshift should represent worker control as capabilities:

```text
supports_start_task
supports_resume_message
supports_live_message
supports_structured_events
supports_graceful_stop
```

Budget pressure should degrade by provider:

```text
live message supported:
  send pressure/stop message into active session

resume message supported:
  wait for current turn/process to finish, then send follow-up resume message if needed

no steer channel:
  stop launching new work, enforce timeout, write wrap-up guidance into run report
```

Do not assume all providers can be steered mid-turn. For v1, prompts should
include the budget policy up front so workers can self-stop even if live
steering is unavailable.
