from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Callable, Sequence, assert_never


DEFAULT_PROVIDERS = ("codex", "claude", "cursor")
DEFAULT_TIMEOUT_SECONDS = 15
CODEXBAR_APP_SUPPORT = "Library/Application Support/com.steipete.codexbar"
CODEXBAR_WIDGET_SNAPSHOTS = (
    "Library/Group Containers/Y5PE65HELJ.com.steipete.codexbar/widget-snapshot.json",
    "Library/Group Containers/group.com.steipete.codexbar/widget-snapshot.json",
)
WINDOW_LABELS = {
    "codex": {
        "primary": "session",
        "secondary": "weekly",
    },
    "claude": {
        "primary": "session",
        "secondary": "weekly",
    },
    "cursor": {
        "primary": "total",
        "secondary": "Auto",
        "tertiary": "API",
    },
}


@dataclass(frozen=True)
class UsageWindow:
    name: str
    used_percent: int | float
    resets_at: str
    reset_description: str
    window_minutes: int | None


@dataclass(frozen=True)
class ProviderUsage:
    provider: str
    source: str
    windows: tuple[UsageWindow, ...]
    updated_at: str
    account: str


@dataclass(frozen=True)
class ProviderUsageError:
    provider: str
    message: str


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
ProviderUsageResult = ProviderUsage | ProviderUsageError


def fetch_provider_usage(
    providers: Sequence[str] = DEFAULT_PROVIDERS,
    *,
    runner: Runner | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[ProviderUsage, ...]:
    run = runner or _runner_with_timeout(timeout_seconds)
    usages: list[ProviderUsage] = []
    for provider in providers:
        usages.append(fetch_one_provider_usage(provider, runner=run))
    return tuple(usages)


def fetch_provider_usage_results(
    providers: Sequence[str] = DEFAULT_PROVIDERS,
    *,
    runner: Runner | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    source: str = "auto",
) -> tuple[ProviderUsageResult, ...]:
    assert source in {"auto", "cache", "live"}

    run = runner or _runner_with_timeout(timeout_seconds)
    ordered_providers = tuple(providers)
    results: dict[str, ProviderUsageResult] = {}

    if source in {"auto", "cache"}:
        for provider in ordered_providers:
            cached = fetch_cached_provider_usage(provider)
            if cached is not None:
                results[provider] = cached
            elif source == "cache":
                results[provider] = ProviderUsageError(provider, "no codexbar cache")

    live_providers = tuple(
        provider for provider in ordered_providers if provider not in results
    )
    if not live_providers:
        return tuple(results[provider] for provider in ordered_providers)

    with ThreadPoolExecutor(max_workers=max(1, len(ordered_providers))) as executor:
        future_to_provider = {
            executor.submit(fetch_one_provider_usage, provider, runner=run): provider
            for provider in live_providers
        }
        for future in as_completed(future_to_provider):
            provider = future_to_provider[future]
            try:
                results[provider] = future.result()
            except subprocess.TimeoutExpired:
                results[provider] = ProviderUsageError(
                    provider=provider,
                    message=f"timed out after {timeout_seconds}s",
                )
            except RuntimeError as exc:
                msg = str(exc)
                pfx = f"{provider}: "
                if msg.startswith(pfx):
                    msg = msg.removeprefix(pfx)
                results[provider] = ProviderUsageError(provider=provider, message=msg)
            except Exception as exc:
                results[provider] = ProviderUsageError(
                    provider=provider, message=str(exc)
                )

    return tuple(results[provider] for provider in ordered_providers)


def fetch_cached_provider_usage(provider: str) -> ProviderUsage | None:
    snapshot = _load_latest_widget_snapshot()
    if snapshot is not None:
        for entry in snapshot.get("entries", ()):
            if entry.get("provider") == provider:
                return _usage_from_widget_entry(provider, entry)

    history = _load_history(provider)
    if history is not None:
        return _usage_from_history(provider, history)

    return None


def fetch_one_provider_usage(
    provider: str, *, runner: Runner | None = None
) -> ProviderUsage:
    run = runner or _runner_with_timeout(DEFAULT_TIMEOUT_SECONDS)
    result = run(
        [
            "codexbar",
            "usage",
            "--provider",
            provider,
            "--format",
            "json",
        ]
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "codexbar failed").strip()
        raise RuntimeError(f"{provider}: {message}")

    payload = _loads_json_array(result.stdout)
    if not payload:
        raise RuntimeError(f"{provider}: codexbar returned no usage")

    item = payload[0]
    if "error" in item:
        message = item["error"].get("message", "unknown provider error")
        raise RuntimeError(f"{provider}: {message}")

    usage = item.get("usage", {})
    windows = tuple(
        _parse_window(_window_label(provider, name), usage[name])
        for name in ("primary", "secondary", "tertiary")
        if usage.get(name) is not None
    )
    return ProviderUsage(
        provider=str(item.get("provider", provider)),
        source=str(item.get("source", "")),
        windows=windows,
        updated_at=str(usage.get("updatedAt", "")),
        account=str(
            usage.get("accountEmail")
            or usage.get("identity", {}).get("accountEmail", "")
        ),
    )


def format_provider_usage(usages: Sequence[ProviderUsageResult]) -> str:
    lines: list[str] = []
    for item in usages:
        match item:
            case ProviderUsageError(provider=name, message=msg):
                lines.append(f"{name}\terror\t{msg}")
            case ProviderUsage() as u:
                if not u.windows:
                    lines.append(f"{u.provider}\tno windows")
                    continue
                for window in u.windows:
                    reset = window.reset_description or window.resets_at or "unknown reset"
                    reserve = reserve_percent(window, u.updated_at)
                    reserve_text = f"\t{round(reserve)}% reserve" if reserve > 0 else ""
                    remaining = remaining_percent(window)
                    lines.append(
                        f"{u.provider}\t{window.name}\t{remaining}% left\t{reset}{reserve_text}"
                    )
            case _:
                assert_never(item)
    return "\n".join(lines)


def remaining_percent(window: UsageWindow) -> int | float:
    used = float(window.used_percent)
    remaining = float(max(0, min(100, 100 - used)))
    return int(remaining) if remaining.is_integer() else remaining


def reserve_percent(window: UsageWindow, updated_at: str) -> float:
    if not window.window_minutes or not window.resets_at or not updated_at:
        return 0

    reset = _parse_datetime(window.resets_at)
    updated = _parse_datetime(updated_at)
    if reset is None or updated is None:
        return 0

    remaining_minutes = (reset - updated).total_seconds() / 60
    elapsed_minutes = window.window_minutes - remaining_minutes
    ideal_used = max(0, min(100, (elapsed_minutes / window.window_minutes) * 100))
    used = float(window.used_percent)
    return max(0, ideal_used - used)


def _load_latest_widget_snapshot() -> dict | None:
    snapshots: list[dict] = []
    for relative in CODEXBAR_WIDGET_SNAPSHOTS:
        path = Path.home() / relative
        if not path.exists():
            continue
        try:
            snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    if not snapshots:
        return None
    return max(snapshots, key=lambda snapshot: str(snapshot.get("generatedAt", "")))


def _load_history(provider: str) -> dict | None:
    path = Path.home() / CODEXBAR_APP_SUPPORT / "history" / f"{provider}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _usage_from_widget_entry(provider: str, entry: dict) -> ProviderUsage:
    names = _window_names_from_usage_rows(entry.get("usageRows", ()))
    windows = []
    for index, key in enumerate(("primary", "secondary", "tertiary")):
        raw = entry.get(key)
        if raw is None:
            continue
        windows.append(_parse_window(_window_label(provider, key, names.get(key)), raw))
    return ProviderUsage(
        provider=provider,
        source="codexbar-cache",
        windows=tuple(windows),
        updated_at=str(entry.get("updatedAt", "")),
        account="",
    )


def _usage_from_history(provider: str, history: dict) -> ProviderUsage | None:
    windows = _history_windows(history)
    if not windows:
        return None
    updated_at = max(
        (
            str(window["entries"][-1].get("capturedAt", ""))
            for window in windows
            if window.get("entries")
        ),
        default="",
    )
    return ProviderUsage(
        provider=provider,
        source="codexbar-history",
        windows=tuple(
            _parse_history_window(provider, window)
            for window in windows
            if window.get("entries")
        ),
        updated_at=updated_at,
        account=str(history.get("preferredAccountKey", "")),
    )


def _history_windows(history: dict) -> list[dict]:
    account_key = history.get("preferredAccountKey")
    accounts = history.get("accounts", {})
    if account_key and account_key in accounts:
        return list(accounts[account_key])
    for windows in accounts.values():
        if windows:
            return list(windows)
    return list(history.get("unscoped", ()))


def _parse_history_window(provider: str, raw: dict) -> UsageWindow:
    latest = raw["entries"][-1]
    name = str(raw.get("name", ""))
    return UsageWindow(
        name=_window_label(provider, name)
        if name in {"primary", "secondary", "tertiary"}
        else name,
        used_percent=latest.get("usedPercent", 0),
        resets_at=str(latest.get("resetsAt", "")),
        reset_description="",
        window_minutes=raw.get("windowMinutes"),
    )


def _window_names_from_usage_rows(rows: object) -> dict[str, str]:
    if not isinstance(rows, list):
        return {}
    keys = ("primary", "secondary", "tertiary")
    names: dict[str, str] = {}
    for key, row in zip(keys, rows):
        if isinstance(row, dict):
            names[key] = str(row.get("id") or row.get("title") or key)
    return names


def _window_label(provider: str, key: str, fallback: str | None = None) -> str:
    return WINDOW_LABELS.get(provider, {}).get(key, fallback or key)


def _runner_with_timeout(timeout_seconds: int) -> Runner:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(args),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

    return run


def _loads_json_array(stdout: str) -> list[dict]:
    text = stdout.strip()
    start = text.find("[")
    if start > 0:
        text = text[start:]
    return json.loads(text)


def _parse_window(name: str, raw: dict) -> UsageWindow:
    return UsageWindow(
        name=name,
        used_percent=raw.get("usedPercent", 0),
        resets_at=str(raw.get("resetsAt", "")),
        reset_description=str(raw.get("resetDescription", "")),
        window_minutes=raw.get("windowMinutes"),
    )


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
