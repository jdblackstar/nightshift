from __future__ import annotations

from pathlib import Path

from nightshift.config import load_config


MAX_IMPORT_BYTES = 200_000


def render_context(repo_path: Path) -> str:
    root = repo_path.expanduser().resolve()
    config = load_config()

    parts = [
        "# Nightshift Agent Context",
        "",
        "This context was assembled from global Nightshift config and repo-local imports.",
        "",
        "## Guardrails",
        "",
        "Allowed work:",
        *[f"- {item}" for item in config.guardrails.allowed_work],
        "",
        "Blocked paths:",
        *[f"- {item}" for item in config.guardrails.blocked_paths],
    ]

    parts.extend(
        _render_import_group(root, "Markdown Imports", config.context.markdown)
    )
    parts.extend(_render_import_group(root, "Skill Imports", config.context.skills))

    return "\n".join(parts).rstrip() + "\n"


def _render_import_group(
    root: Path, title: str, patterns: tuple[str, ...]
) -> list[str]:
    parts = ["", f"## {title}"]

    matched = False
    for pattern in patterns:
        paths = sorted(root.glob(pattern))
        if not paths:
            parts.extend(["", f"### Missing: `{pattern}`", ""])
            continue

        for path in paths:
            if not path.is_file():
                continue
            matched = True
            rel_path = path.relative_to(root)
            parts.extend(["", f"### `{rel_path}`", ""])
            parts.append(_read_import(path))

    if not matched:
        parts.extend(["", "_No files imported._"])

    return parts


def _read_import(path: Path) -> str:
    raw = path.read_bytes()
    if len(raw) > MAX_IMPORT_BYTES:
        raw = raw[:MAX_IMPORT_BYTES]
        suffix = b"\n\n[truncated by Nightshift]\n"
    else:
        suffix = b""
    return (raw + suffix).decode("utf-8", errors="replace").rstrip()
