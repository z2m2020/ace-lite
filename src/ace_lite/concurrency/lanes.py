"""Lane-based thread pools for lightweight task isolation."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(frozen=True, slots=True)
class LaneConfig:
    """Runtime config for a logical execution lane."""

    name: str
    max_workers: int
    reserved: bool = False


class LanePool:
    """A small lane-based executor pool.

    Each lane owns its own `ThreadPoolExecutor`, enabling physical isolation
    between task classes without shared global queues.
    """

    def __init__(self, lanes: list[LaneConfig] | tuple[LaneConfig, ...]) -> None:
        self._lock = Lock()
        self._closed = False
        self._lanes: dict[str, ThreadPoolExecutor] = {}

        for lane in lanes:
            lane_name = str(lane.name).strip()
            if not lane_name:
                continue
            if lane_name in self._lanes:
                raise ValueError(f"Duplicate lane name: {lane_name}")
            self._lanes[lane_name] = ThreadPoolExecutor(
                max_workers=max(1, int(lane.max_workers)),
                thread_name_prefix=f"ace-lite-{lane_name}",
            )

        if not self._lanes:
            raise ValueError("LanePool requires at least one lane")

    @property
    def lanes(self) -> tuple[str, ...]:
        return tuple(self._lanes.keys())

    def submit(
        self,
        lane: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Future[Any]:
        lane_name = str(lane).strip()
        with self._lock:
            if self._closed:
                raise RuntimeError("LanePool is closed")
            executor = self._lanes.get(lane_name)
        if executor is None:
            raise KeyError(f"Unknown lane: {lane_name}")
        return executor.submit(fn, *args, **kwargs)

    def shutdown(self, *, wait: bool = True, cancel_futures: bool = False) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            executors = list(self._lanes.values())
        for executor in executors:
            executor.shutdown(wait=wait, cancel_futures=cancel_futures)


_shared_memory_lane_pool: LanePool | None = None
_shared_memory_lane_pool_lock = Lock()


def build_memory_lane_pool() -> LanePool:
    """Return a shared memory lane pool (`main`/`sub`) for providers."""

    global _shared_memory_lane_pool
    with _shared_memory_lane_pool_lock:
        if _shared_memory_lane_pool is None:
            _shared_memory_lane_pool = LanePool(
                [
                    LaneConfig(name="main", max_workers=2, reserved=True),
                    LaneConfig(name="sub", max_workers=2, reserved=False),
                ]
            )
        return _shared_memory_lane_pool

