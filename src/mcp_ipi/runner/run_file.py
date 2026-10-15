"""The run file: one JSON file per run at its canonical path, the source of truth for every metric."""

from pathlib import Path

from pydantic import BaseModel

from mcp_ipi.agent import Message, Usage
from mcp_ipi.suites import TaskDifficulty

BENCHMARK_VERSION = "1.0.0"
"""The benchmark's version, recorded in every run file; raise it when a change makes runs incomparable."""


class RunResult(BaseModel):
    """The complete outcome of one run, as written to its run file: the fields of the run file table in PROJECT.md."""

    suite_name: str
    pipeline_name: str
    model: str
    provider: str | list[str] | None
    finish_reasons: list[str | None]
    defense: str
    user_task_id: str
    injection_task_id: str | None
    attack: str
    user_task_difficulty: TaskDifficulty
    injection_task_difficulty: TaskDifficulty | None
    injections: dict[str, str]
    messages: list[Message]
    utility: bool | None
    security: bool | None
    hit_iteration_limit: bool
    usage: Usage
    error: str | None
    temperature: float
    benchmark_version: str
    duration: float
    evaluation_timestamp: str


def pipeline_name(model: str, defense: str) -> str:
    """Name a pipeline by its model ID with `/` as `_`, plus `-<defense>` unless the defense is `none`."""
    name = model.replace("/", "_")
    return name if defense == "none" else f"{name}-{defense}"


def run_path(
    logdir: Path,
    pipeline_name: str,
    suite_name: str,
    user_task_id: str,
    attack: str,
    injection_task_id: str | None,
) -> Path:
    """Return a run's file, `<logdir>/<pipeline>/<suite>/<user_task>/<attack>/<injection_task>.json`.

    A missing injection task is `none`. Nothing else builds a run's path.
    """
    return logdir / pipeline_name / suite_name / user_task_id / attack / f"{injection_task_id or 'none'}.json"


def save_run(result: RunResult, path: Path) -> None:
    """Write the run file atomically: to `<name>.json.tmp` first, then renamed over `<name>.json`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(result.model_dump_json(indent=2))
    tmp_path.replace(path)


def load_run(path: Path) -> RunResult:
    """Read a run file back into the `RunResult` it was written from."""
    return RunResult.model_validate_json(path.read_text())


def should_run(path: Path, force: bool) -> bool:
    """Whether a run must be done: always when forced, else when its file is missing or records an error."""
    return force or not path.exists() or load_run(path).error is not None
