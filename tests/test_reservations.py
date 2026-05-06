from datetime import datetime, timezone
from pathlib import Path

from nightshift.reservations import (
    ACTIVE,
    EXPIRED,
    RELEASED,
    list_reservations,
    release_reservation,
    reserve_budget,
    reserved_percent,
)


def test_reserve_budget_creates_active_reservation(tmp_path: Path) -> None:
    now = datetime(2026, 5, 4, 0, 0, tzinfo=timezone.utc)

    reservation = reserve_budget(
        tmp_path,
        provider="codex",
        window="weekly",
        repo="nightshift",
        reserved_percent=5,
        ttl_minutes=90,
        now=now,
    )

    assert reservation.provider == "codex"
    assert reservation.window == "weekly"
    assert reservation.reserved_percent == 5
    assert reservation.status == ACTIVE
    assert reserved_percent(tmp_path, "codex", "weekly", now=now) == 5


def test_release_reservation_removes_it_from_active_budget(tmp_path: Path) -> None:
    now = datetime(2026, 5, 4, 0, 0, tzinfo=timezone.utc)
    reservation = reserve_budget(
        tmp_path,
        provider="codex",
        window="weekly",
        repo="nightshift",
        reserved_percent=5,
        ttl_minutes=90,
        now=now,
    )

    released = release_reservation(tmp_path, reservation.id, now=now)

    assert released.status == RELEASED
    assert reserved_percent(tmp_path, "codex", "weekly", now=now) == 0
    assert (
        list_reservations(tmp_path, include_inactive=True, now=now)[0].status
        == RELEASED
    )


def test_expired_reservation_does_not_count_against_budget(tmp_path: Path) -> None:
    now = datetime(2026, 5, 4, 0, 0, tzinfo=timezone.utc)
    later = datetime(2026, 5, 4, 2, 0, tzinfo=timezone.utc)
    reserve_budget(
        tmp_path,
        provider="codex",
        window="weekly",
        repo="nightshift",
        reserved_percent=5,
        ttl_minutes=30,
        now=now,
    )

    assert reserved_percent(tmp_path, "codex", "weekly", now=later) == 0
    assert (
        list_reservations(tmp_path, include_inactive=True, now=later)[0].status
        == EXPIRED
    )
