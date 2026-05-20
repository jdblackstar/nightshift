from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import json
from pathlib import Path
from typing import Iterator
from uuid import uuid4


RESERVATIONS_FILE = "reservations.json"
RESERVATIONS_LOCK = "reservations.lock"
ACTIVE = "active"
RELEASED = "released"
EXPIRED = "expired"


@dataclass(frozen=True)
class Reservation:
    id: str
    provider: str
    window: str
    reserved_percent: float
    repo: str
    created_at: str
    expires_at: str
    status: str


def reserve_budget(
    state_root: Path,
    *,
    provider: str,
    window: str,
    repo: str,
    reserved_percent: float,
    ttl_minutes: int,
    now: datetime | None = None,
) -> Reservation:
    current_time = now or _now()
    reservation = Reservation(
        id=f"rsv_{uuid4().hex[:12]}",
        provider=provider,
        window=window,
        reserved_percent=reserved_percent,
        repo=repo,
        created_at=_format_time(current_time),
        expires_at=_format_time(current_time + timedelta(minutes=ttl_minutes)),
        status=ACTIVE,
    )
    with _locked_state(state_root) as reservations:
        reservations = _expire_reservations(reservations, current_time)
        reservations.append(reservation)
        _write_reservations(state_root, reservations)
    return reservation


def release_reservation(
    state_root: Path,
    reservation_id: str,
    *,
    now: datetime | None = None,
) -> Reservation:
    current_time = now or _now()
    with _locked_state(state_root) as reservations:
        reservations = _expire_reservations(reservations, current_time)
        updated: list[Reservation] = []
        released: Reservation | None = None
        for reservation in reservations:
            if reservation.id == reservation_id:
                released = Reservation(
                    id=reservation.id,
                    provider=reservation.provider,
                    window=reservation.window,
                    reserved_percent=reservation.reserved_percent,
                    repo=reservation.repo,
                    created_at=reservation.created_at,
                    expires_at=reservation.expires_at,
                    status=RELEASED,
                )
                updated.append(released)
            else:
                updated.append(reservation)
        if released is None:
            raise ValueError(f"reservation not found: {reservation_id}")
        _write_reservations(state_root, updated)
        return released


def list_reservations(
    state_root: Path,
    *,
    include_inactive: bool = False,
    now: datetime | None = None,
) -> tuple[Reservation, ...]:
    current_time = now or _now()
    with _locked_state(state_root) as reservations:
        reservations = _expire_reservations(reservations, current_time)
        _write_reservations(state_root, reservations)
    if include_inactive:
        return tuple(reservations)
    return tuple(
        reservation for reservation in reservations if reservation.status == ACTIVE
    )


def reserved_percent(
    state_root: Path,
    provider: str,
    window: str,
    *,
    now: datetime | None = None,
) -> float:
    return sum(
        reservation.reserved_percent
        for reservation in list_reservations(state_root, now=now)
        if reservation.provider == provider and reservation.window == window
    )


@contextmanager
def _locked_state(state_root: Path) -> Iterator[list[Reservation]]:
    state_root.mkdir(parents=True, exist_ok=True)
    lock_path = state_root / RESERVATIONS_LOCK
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield _read_reservations(state_root)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_reservations(state_root: Path) -> list[Reservation]:
    path = state_root / RESERVATIONS_FILE
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Reservation(**item) for item in data.get("reservations", [])]


def _write_reservations(state_root: Path, reservations: list[Reservation]) -> None:
    path = state_root / RESERVATIONS_FILE
    path.write_text(
        json.dumps(
            {"reservations": [reservation.__dict__ for reservation in reservations]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _expire_reservations(
    reservations: list[Reservation], now: datetime
) -> list[Reservation]:
    updated: list[Reservation] = []
    for reservation in reservations:
        if reservation.status != ACTIVE:
            updated.append(reservation)
            continue
        expires_at = _parse_time(reservation.expires_at)
        if expires_at <= now:
            updated.append(
                Reservation(
                    id=reservation.id,
                    provider=reservation.provider,
                    window=reservation.window,
                    reserved_percent=reservation.reserved_percent,
                    repo=reservation.repo,
                    created_at=reservation.created_at,
                    expires_at=reservation.expires_at,
                    status=EXPIRED,
                )
            )
        else:
            updated.append(reservation)
    return updated


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
