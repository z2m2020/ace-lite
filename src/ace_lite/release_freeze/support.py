from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml


@dataclass(slots=True)
class StepResult:
    name: str
    command: list[str]
    returncode: int
    elapsed_seconds: float
    stdout_path: str
    stderr_path: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def load_yaml_config(*, path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        loaded = {}
    return loaded if isinstance(loaded, dict) else {}


def run_step(*, name: str, command: list[str], cwd: Path, logs_dir: Path) -> StepResult:
    started = perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = perf_counter() - started

    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{name}.stdout.log"
    stderr_path = logs_dir / f"{name}.stderr.log"
    stdout_path.write_text(str(completed.stdout or ""), encoding="utf-8")
    stderr_path.write_text(str(completed.stderr or ""), encoding="utf-8")

    return StepResult(
        name=name,
        command=command,
        returncode=int(completed.returncode),
        elapsed_seconds=round(elapsed, 3),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )


__all__ = ["StepResult", "load_yaml_config", "run_step"]
