from __future__ import annotations

from ace_lite.concurrency import LaneConfig, LanePool


def test_lane_pool_routes_tasks_to_named_lane() -> None:
    pool = LanePool(
        [
            LaneConfig(name="main", max_workers=1, reserved=True),
            LaneConfig(name="sub", max_workers=1),
        ]
    )
    try:
        assert pool.lanes == ("main", "sub")

        main = pool.submit("main", lambda: "main-ok")
        sub = pool.submit("sub", lambda: "sub-ok")

        assert main.result() == "main-ok"
        assert sub.result() == "sub-ok"
    finally:
        pool.shutdown(wait=True)


def test_lane_pool_rejects_unknown_lane() -> None:
    pool = LanePool([LaneConfig(name="main", max_workers=1)])
    try:
        try:
            pool.submit("missing", lambda: None)
            raise AssertionError("expected KeyError for unknown lane")
        except KeyError:
            pass
    finally:
        pool.shutdown(wait=True)


def test_lane_pool_rejects_submit_after_shutdown() -> None:
    pool = LanePool([LaneConfig(name="main", max_workers=1)])
    pool.shutdown(wait=True)
    try:
        pool.submit("main", lambda: None)
        raise AssertionError("expected RuntimeError when pool closed")
    except RuntimeError:
        pass
