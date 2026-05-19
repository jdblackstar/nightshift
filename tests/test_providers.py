from __future__ import annotations

import subprocess

from nightshift.providers import (
    ProviderUsage,
    ProviderUsageError,
    UsageWindow,
    fetch_cached_provider_usage,
    fetch_provider_usage,
    fetch_provider_usage_results,
    format_provider_usage,
    reserve_percent,
)


def test_fetch_provider_usage_uses_codexbar_json() -> None:
    def runner(args):
        provider = args[args.index("--provider") + 1]
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"""
[
  {{
    "provider": "{provider}",
    "source": "web",
    "usage": {{
      "accountEmail": "josh@example.com",
      "primary": {{
        "usedPercent": 12,
        "resetDescription": "soon",
        "resetsAt": "2026-05-04T20:00:00Z",
        "windowMinutes": 300
      }},
      "secondary": null,
      "tertiary": null,
      "updatedAt": "2026-05-04T19:00:00Z"
    }}
  }}
]
""",
            stderr="",
        )

    usages = fetch_provider_usage(("codex", "claude", "cursor"), runner=runner)

    assert [usage.provider for usage in usages] == ["codex", "claude", "cursor"]
    assert usages[0].windows[0].used_percent == 12
    assert usages[0].account == "josh@example.com"


def test_format_provider_usage_is_short() -> None:
    def runner(args):
        provider = args[args.index("--provider") + 1]
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"""
[
  {{
    "provider": "{provider}",
    "source": "web",
    "usage": {{
      "primary": {{"usedPercent": 7, "resetDescription": "tonight"}},
      "secondary": null,
      "tertiary": null
    }}
  }}
]
""",
            stderr="",
        )

    rendered = format_provider_usage(fetch_provider_usage(("cursor",), runner=runner))

    assert rendered == "cursor\ttotal\t93% left\ttonight"


def test_live_provider_usage_normalizes_claude_window_names() -> None:
    def runner(args):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="""
[
  {
    "provider": "claude",
    "source": "claude",
    "usage": {
      "primary": {"usedPercent": 3, "resetDescription": "soon"},
      "secondary": {"usedPercent": 4, "resetDescription": "later"},
      "tertiary": null
    }
  }
]
""",
            stderr="",
        )

    rendered = format_provider_usage(fetch_provider_usage(("claude",), runner=runner))

    assert rendered.splitlines() == [
        "claude\tsession\t97% left\tsoon",
        "claude\tweekly\t96% left\tlater",
    ]


def test_fetch_provider_usage_surfaces_codexbar_errors() -> None:
    def runner(args):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="""
[
  {
    "provider": "cursor",
    "error": {"message": "not logged in"}
  }
]
""",
            stderr="",
        )

    try:
        fetch_provider_usage(("cursor",), runner=runner)
    except RuntimeError as exc:
        assert str(exc) == "cursor: not logged in"
    else:
        raise AssertionError("expected RuntimeError")


def test_fetch_provider_usage_results_handles_malformed_json() -> None:
    def runner(args):
        provider = args[args.index("--provider") + 1]
        if provider == "claude":
            return subprocess.CompletedProcess(
                args=args, returncode=0, stdout="not json", stderr=""
            )
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"""
[
  {{
    "provider": "{provider}",
    "source": "web",
    "usage": {{
      "primary": {{"usedPercent": 1, "resetDescription": "soon"}},
      "secondary": null,
      "tertiary": null
    }}
  }}
]
""",
            stderr="",
        )

    results = fetch_provider_usage_results(
        ("codex", "claude", "cursor"),
        runner=runner,
        source="live",
    )

    assert [result.provider for result in results] == ["codex", "claude", "cursor"]
    assert isinstance(results[0], ProviderUsage)
    assert isinstance(results[1], ProviderUsageError)
    assert isinstance(results[2], ProviderUsage)


def test_fetch_provider_usage_results_handles_os_errors() -> None:
    def runner(args):
        provider = args[args.index("--provider") + 1]
        if provider == "cursor":
            raise FileNotFoundError("codexbar not found")
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"""
[
  {{
    "provider": "{provider}",
    "source": "web",
    "usage": {{
      "primary": {{"usedPercent": 1, "resetDescription": "soon"}},
      "secondary": null,
      "tertiary": null
    }}
  }}
]
""",
            stderr="",
        )

    results = fetch_provider_usage_results(
        ("codex", "claude", "cursor"),
        runner=runner,
        source="live",
    )

    assert [result.provider for result in results] == ["codex", "claude", "cursor"]
    assert isinstance(results[2], ProviderUsageError)
    assert results[2].message == "codexbar not found"


def test_fetch_provider_usage_results_returns_partial_errors() -> None:
    def runner(args):
        provider = args[args.index("--provider") + 1]
        if provider == "claude":
            return subprocess.CompletedProcess(
                args=args, returncode=1, stdout="", stderr="slow"
            )
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"""
[
  {{
    "provider": "{provider}",
    "source": "web",
    "usage": {{
      "primary": {{"usedPercent": 1, "resetDescription": "soon"}},
      "secondary": null,
      "tertiary": null
    }}
  }}
]
""",
            stderr="",
        )

    results = fetch_provider_usage_results(
        ("codex", "claude", "cursor"),
        runner=runner,
        source="live",
    )

    assert [result.provider for result in results] == ["codex", "claude", "cursor"]
    assert isinstance(results[1], ProviderUsageError)
    assert format_provider_usage(results).splitlines()[1] == "claude\terror\tslow"


def test_cached_provider_usage_reads_latest_widget_snapshot(
    tmp_path, monkeypatch
) -> None:
    home = tmp_path
    snapshot_path = (
        home
        / "Library/Group Containers/Y5PE65HELJ.com.steipete.codexbar/widget-snapshot.json"
    )
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(
        """
{
  "generatedAt": "2026-05-04T19:47:44Z",
  "entries": [
    {
      "provider": "codex",
      "updatedAt": "2026-05-04T19:47:43Z",
      "usageRows": [{"id": "session"}, {"id": "weekly"}],
      "primary": {"usedPercent": 34, "resetsAt": "2026-05-04T23:15:39Z"},
      "secondary": {"usedPercent": 13, "resetsAt": "2026-05-07T20:32:34Z"}
    }
  ]
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    usage = fetch_cached_provider_usage("codex")

    assert usage is not None
    assert usage.source == "codexbar-cache"
    assert usage.windows[0].name == "session"
    assert usage.windows[0].used_percent == 34


def test_cached_provider_usage_falls_back_to_history(tmp_path, monkeypatch) -> None:
    home = tmp_path
    history_path = (
        home / "Library/Application Support/com.steipete.codexbar/history/claude.json"
    )
    history_path.parent.mkdir(parents=True)
    history_path.write_text(
        """
{
  "accounts": {},
  "unscoped": [
    {
      "name": "weekly",
      "windowMinutes": 10080,
      "entries": [
        {
          "capturedAt": "2026-05-04T19:45:05Z",
          "resetsAt": "2026-05-10T14:00:00Z",
          "usedPercent": 11
        }
      ]
    }
  ]
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    usage = fetch_cached_provider_usage("claude")

    assert usage is not None
    assert usage.source == "codexbar-history"
    assert usage.windows[0].name == "weekly"
    assert usage.windows[0].used_percent == 11


def test_cached_history_normalizes_provider_window_names(tmp_path, monkeypatch) -> None:
    home = tmp_path
    history_path = (
        home / "Library/Application Support/com.steipete.codexbar/history/codex.json"
    )
    history_path.parent.mkdir(parents=True)
    history_path.write_text(
        """
{
  "accounts": {},
  "unscoped": [
    {
      "name": "secondary",
      "windowMinutes": 10080,
      "entries": [
        {
          "capturedAt": "2026-05-04T19:45:05Z",
          "resetsAt": "2026-05-10T14:00:00Z",
          "usedPercent": 11
        }
      ]
    }
  ]
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    usage = fetch_cached_provider_usage("codex")

    assert usage is not None
    assert usage.windows[0].name == "weekly"


def test_cached_cursor_usage_uses_expected_window_names(tmp_path, monkeypatch) -> None:
    home = tmp_path
    snapshot_path = (
        home
        / "Library/Group Containers/Y5PE65HELJ.com.steipete.codexbar/widget-snapshot.json"
    )
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(
        """
{
  "entries": [
    {
      "provider": "cursor",
      "primary": {"usedPercent": 1},
      "secondary": {"usedPercent": 2},
      "tertiary": {"usedPercent": 3}
    }
  ]
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    usage = fetch_cached_provider_usage("cursor")

    assert usage is not None
    assert [window.name for window in usage.windows] == ["total", "Auto", "API"]


def test_format_provider_usage_includes_reserve_when_behind_pace(
    tmp_path, monkeypatch
) -> None:
    home = tmp_path
    snapshot_path = (
        home
        / "Library/Group Containers/Y5PE65HELJ.com.steipete.codexbar/widget-snapshot.json"
    )
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text(
        """
{
  "entries": [
    {
      "provider": "codex",
      "updatedAt": "2026-05-04T19:51:21Z",
      "secondary": {
        "usedPercent": 14,
        "resetsAt": "2026-05-07T20:32:34Z",
        "windowMinutes": 10080,
        "resetDescription": "May 7, 2026 at 13:32"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    usage = fetch_cached_provider_usage("codex")

    assert usage is not None
    assert round(reserve_percent(usage.windows[0], usage.updated_at)) == 43
    assert format_provider_usage((usage,)) == (
        "codex\tweekly\t86% left\tMay 7, 2026 at 13:32\t43% reserve"
    )


def test_format_provider_usage_omits_reserve_when_rounded_to_zero() -> None:
    window = UsageWindow(
        name="weekly",
        used_percent=50,
        resets_at="2026-05-07T20:32:34Z",
        reset_description="reset",
        window_minutes=1000,
    )
    usage = ProviderUsage(
        provider="codex",
        source="cache",
        windows=(window,),
        updated_at="2026-05-07T12:13:34Z",
        account="",
    )

    reserve = reserve_percent(window, usage.updated_at)
    assert 0 < reserve < 0.5
    assert round(reserve) == 0
    assert format_provider_usage((usage,)) == "codex\tweekly\t50% left\treset"
