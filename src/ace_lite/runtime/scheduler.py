"""Cron + heartbeat task scheduler."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_cron_field(
    value: str,
    *,
    minimum: int,
    maximum: int,
) -> set[int]:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("empty cron field")

    values: set[int] = set()
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    for part in parts:
        if part == "*":
            values.update(range(minimum, maximum + 1))
            continue

        step = 1
        base = part
        if "/" in part:
            base, step_text = part.split("/", 1)
            try:
                step = max(1, int(step_text.strip()))
            except ValueError as exc:  # pragma: no cover - defensive path
                raise ValueError(f"invalid cron step: {part}") from exc

        if base in {"*", ""}:
            start = minimum
            end = maximum
        elif "-" in base:
            left, right = base.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
        else:
            start = int(base.strip())
            end = start

        if start < minimum or end > maximum or start > end:
            raise ValueError(
                f"cron field out of range: {part} (expected {minimum}-{maximum})"
            )
        values.update(range(start, end + 1, step))

    if not values:
        raise ValueError(f"cron field resolved empty: {raw}")
    return values


@dataclass(frozen=True, slots=True)
class CronSchedule:
    expression: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]

    @classmethod
    def parse(cls, expression: str) -> CronSchedule:
        raw = str(expression or "").strip()
        parts = [part for part in raw.split() if part]
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression '{raw}', expected 5 fields."
            )

        minute_values = _parse_cron_field(parts[0], minimum=0, maximum=59)
        hour_values = _parse_cron_field(parts[1], minimum=0, maximum=23)
        day_values = _parse_cron_field(parts[2], minimum=1, maximum=31)
        month_values = _parse_cron_field(parts[3], minimum=1, maximum=12)
        weekday_values = _parse_cron_field(parts[4], minimum=0, maximum=7)
        normalized_weekdays = {0 if day == 7 else day for day in weekday_values}

        return cls(
            expression=raw,
            minutes=frozenset(minute_values),
            hours=frozenset(hour_values),
            days=frozenset(day_values),
            months=frozenset(month_values),
            weekdays=frozenset(normalized_weekdays),
        )

    def matches(self, moment: datetime) -> bool:
        current = _to_utc(moment)
        cron_weekday = (current.weekday() + 1) % 7  # Sunday=0, Monday=1, ...
        return (
            current.minute in self.minutes
            and current.hour in self.hours
            and current.day in self.days
            and current.month in self.months
            and cron_weekday in self.weekdays
        )

    def next_after(self, moment: datetime) -> datetime:
        current = _to_utc(moment).replace(second=0, microsecond=0) + timedelta(minutes=1)
        limit = current + timedelta(days=366 * 3)
        while current <= limit:
            if self.matches(current):
                return current
            current += timedelta(minutes=1)
        raise RuntimeError(
            f"unable to resolve next cron trigger for '{self.expression}' within search window"
        )


TaskMode = Literal["heartbeat", "cron"]
TaskAction = Callable[[str, datetime], Any]


@dataclass(frozen=True, slots=True)
class ScheduledTask:
    name: str
    mode: TaskMode
    action: TaskAction
    enabled: bool = True
    heartbeat_interval_seconds: float = 0.0
    cron: CronSchedule | None = None
    run_on_start: bool = False


@dataclass(frozen=True, slots=True)
class SchedulerRun:
    name: str
    mode: TaskMode
    trigger_at: str
    success: bool
    error: str = ""


@dataclass(frozen=True, slots=True)
class SchedulerTickResult:
    now: str
    runs: tuple[SchedulerRun, ...]


@dataclass(slots=True)
class _TaskState:
    next_run_at: datetime | None = None


class TaskScheduler:
    """In-process scheduler for heartbeat and cron tasks."""

    def __init__(self) -> None:
        self._tasks: list[ScheduledTask] = []
        self._states: dict[str, _TaskState] = {}

    def add_heartbeat_task(
        self,
        *,
        name: str,
        interval_seconds: float,
        action: TaskAction,
        run_on_start: bool = True,
        enabled: bool = True,
    ) -> None:
        task_name = str(name or "").strip()
        if not task_name:
            raise ValueError("heartbeat task name cannot be empty")
        if interval_seconds <= 0:
            raise ValueError("heartbeat interval must be > 0")
        self._ensure_unique_name(task_name)
        self._tasks.append(
            ScheduledTask(
                name=task_name,
                mode="heartbeat",
                action=action,
                enabled=bool(enabled),
                heartbeat_interval_seconds=float(interval_seconds),
                run_on_start=bool(run_on_start),
            )
        )
        self._states[task_name] = _TaskState()

    def add_cron_task(
        self,
        *,
        name: str,
        cron: str,
        action: TaskAction,
        enabled: bool = True,
    ) -> None:
        task_name = str(name or "").strip()
        if not task_name:
            raise ValueError("cron task name cannot be empty")
        self._ensure_unique_name(task_name)
        schedule = CronSchedule.parse(cron)
        self._tasks.append(
            ScheduledTask(
                name=task_name,
                mode="cron",
                action=action,
                enabled=bool(enabled),
                cron=schedule,
            )
        )
        self._states[task_name] = _TaskState()

    def tick(self, *, now: datetime | None = None) -> SchedulerTickResult:
        moment = _to_utc(now or datetime.now(timezone.utc))
        ordered = sorted(self._tasks, key=lambda task: task.name)
        runs: list[SchedulerRun] = []

        for task in ordered:
            if not task.enabled:
                continue
            state = self._states.setdefault(task.name, _TaskState())
            trigger_at = self._resolve_due_time(task=task, state=state, now=moment)
            if trigger_at is None:
                continue
            success = True
            error_text = ""
            try:
                task.action(task.name, trigger_at)
            except Exception as exc:  # pragma: no cover - defensive path
                success = False
                error_text = f"{exc.__class__.__name__}: {exc}"

            runs.append(
                SchedulerRun(
                    name=task.name,
                    mode=task.mode,
                    trigger_at=trigger_at.isoformat(),
                    success=success,
                    error=error_text,
                )
            )

            if task.mode == "heartbeat":
                state.next_run_at = trigger_at + timedelta(
                    seconds=task.heartbeat_interval_seconds
                )
            else:
                cron = task.cron
                if cron is None:  # pragma: no cover - typed invariant
                    raise RuntimeError("scheduled task missing cron expression")
                state.next_run_at = cron.next_after(trigger_at)

        return SchedulerTickResult(now=moment.isoformat(), runs=tuple(runs))

    def _resolve_due_time(
        self,
        *,
        task: ScheduledTask,
        state: _TaskState,
        now: datetime,
    ) -> datetime | None:
        due = state.next_run_at
        if task.mode == "heartbeat":
            if due is None:
                if task.run_on_start:
                    return now
                state.next_run_at = now + timedelta(
                    seconds=task.heartbeat_interval_seconds
                )
                return None
            if now >= due:
                return due
            return None

        schedule = task.cron
        if schedule is None:
            return None
        if due is None:
            due = schedule.next_after(now - timedelta(minutes=1))
            state.next_run_at = due
        if now >= due:
            return due
        return None

    def _ensure_unique_name(self, name: str) -> None:
        if any(task.name == name for task in self._tasks):
            raise ValueError(f"duplicate task name: {name}")
