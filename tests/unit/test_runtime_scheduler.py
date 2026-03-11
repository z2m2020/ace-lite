from __future__ import annotations

from datetime import datetime, timezone

from ace_lite.runtime.scheduler import CronSchedule, TaskScheduler


def test_cron_schedule_parse_and_match() -> None:
    schedule = CronSchedule.parse("*/5 * * * *")
    assert schedule.matches(datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc))
    assert schedule.matches(datetime(2026, 2, 13, 10, 5, tzinfo=timezone.utc))
    assert not schedule.matches(datetime(2026, 2, 13, 10, 3, tzinfo=timezone.utc))


def test_scheduler_runs_heartbeat_on_start_and_interval() -> None:
    scheduler = TaskScheduler()
    invocations: list[str] = []

    def _action(name: str, trigger_at: datetime) -> None:
        invocations.append(f"{name}@{trigger_at.isoformat()}")

    scheduler.add_heartbeat_task(
        name="heartbeat",
        interval_seconds=5,
        action=_action,
        run_on_start=True,
    )

    tick1 = scheduler.tick(now=datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc))
    tick2 = scheduler.tick(now=datetime(2026, 2, 13, 10, 0, 4, tzinfo=timezone.utc))
    tick3 = scheduler.tick(now=datetime(2026, 2, 13, 10, 0, 5, tzinfo=timezone.utc))

    assert len(tick1.runs) == 1
    assert len(tick2.runs) == 0
    assert len(tick3.runs) == 1
    assert len(invocations) == 2


def test_scheduler_runs_cron_when_due() -> None:
    scheduler = TaskScheduler()
    invocations: list[str] = []

    def _action(name: str, trigger_at: datetime) -> None:
        invocations.append(f"{name}@{trigger_at.isoformat()}")

    scheduler.add_cron_task(name="cron5", cron="*/5 * * * *", action=_action)

    tick1 = scheduler.tick(now=datetime(2026, 2, 13, 10, 2, tzinfo=timezone.utc))
    tick2 = scheduler.tick(now=datetime(2026, 2, 13, 10, 5, tzinfo=timezone.utc))
    tick3 = scheduler.tick(now=datetime(2026, 2, 13, 10, 10, tzinfo=timezone.utc))

    assert len(tick1.runs) == 0
    assert len(tick2.runs) == 1
    assert len(tick3.runs) == 1
    assert len(invocations) == 2


def test_scheduler_isolates_task_failures() -> None:
    scheduler = TaskScheduler()

    def _ok(name: str, trigger_at: datetime) -> None:
        return None

    def _boom(name: str, trigger_at: datetime) -> None:
        raise RuntimeError("boom")

    scheduler.add_heartbeat_task(
        name="a-ok",
        interval_seconds=1,
        action=_ok,
        run_on_start=True,
    )
    scheduler.add_heartbeat_task(
        name="b-fail",
        interval_seconds=1,
        action=_boom,
        run_on_start=True,
    )

    tick = scheduler.tick(now=datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc))
    by_name = {run.name: run for run in tick.runs}
    assert by_name["a-ok"].success is True
    assert by_name["b-fail"].success is False
    assert "RuntimeError" in by_name["b-fail"].error
