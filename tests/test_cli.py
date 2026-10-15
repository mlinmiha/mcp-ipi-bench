"""Tests for the CLI where no real model is called: `ipi benchmark` with an unknown model, name, task ID or pairs
value, `check-suite`, `ipi sweep --dry-run`, and `ipi sweep` with a scripted fake model."""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from mcp_ipi.agent import Message, State, Usage
from mcp_ipi.cli import cli
from mcp_ipi.mcp import MCPRuntime
from mcp_ipi.runner import RunResult, RunSpec, save_run
from mcp_ipi.suites import SUITES, TaskDifficulty

MAIN_SWEEP = Path(__file__).parents[1] / "sweeps" / "main.yaml"
MAIN_WEAK_ATTACKS_SWEEP = Path(__file__).parents[1] / "sweeps" / "main-weak-attacks.yaml"
PILOT_ATTACKS_SWEEP = Path(__file__).parents[1] / "sweeps" / "pilot-attacks.yaml"
PILOT_TASKS_SWEEP = Path(__file__).parents[1] / "sweeps" / "pilot-tasks.yaml"
PILOT_DEFENSES_SWEEP = Path(__file__).parents[1] / "sweeps" / "pilot-defenses.yaml"


@pytest.mark.parametrize(
    "flags",
    [
        ["--model", "openai/gpt-5.4-mni"],
        ["--suite", "banking"],
        ["--defense", "firewall"],
        ["--attack", "jailbreak"],
        ["-ut", "email_user_task_99"],
        ["-it", "email_injection_task_99"],
        ["-ut", "email_user_task_99", "--max-workers", "4"],
        ["-ut", "web_injection_task_0"],
        ["--pairs", "all"],
    ],
)
def test_an_unknown_model_name_pairs_value_or_task_id_exits_before_any_run(
    flags: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Without a key, building the model would raise KeyError instead of exiting.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(SystemExit):
        cli(["benchmark", "--model", "openai/gpt-5.4-mini", "--logdir", str(tmp_path), *flags])

    assert list(tmp_path.iterdir()) == []


def test_check_suite_on_workspace_prints_the_ok_line(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    cli(["check-suite"])

    assert capsys.readouterr().out == "workspace: 50 user tasks, 25 injection tasks, 250 pairs OK\n"


def test_check_suite_on_a_broken_suite_prints_its_problem_and_exits_non_zero(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    workspace = SUITES["workspace"]
    broken_task = replace(workspace.user_tasks[0], check=lambda *_: False)
    monkeypatch.setitem(
        SUITES, "broken", replace(workspace, name="broken", user_tasks=(broken_task, *workspace.user_tasks[1:]))
    )

    with pytest.raises(SystemExit) as exit_info:
        cli(["check-suite", "--suite", "broken"])

    assert exit_info.value.code == 1
    assert capsys.readouterr().out == f"{broken_task.id}: ground truth does not pass its check\n"


def write_sweep(tmp_path: Path, source: Path = MAIN_SWEEP, **changes: Any) -> Path:
    """Write a copy of `source` with its logdir in `tmp_path` and these keys changed."""
    sweep = yaml.safe_load(source.read_text()) | {"logdir": str(tmp_path / "runs")} | changes
    path = tmp_path / "sweep.yaml"
    path.write_text(yaml.safe_dump(sweep))
    return path


def dry_run_lines(capsys: pytest.CaptureFixture[str]) -> list[list[str]]:
    return [line.rsplit(maxsplit=3) for line in capsys.readouterr().out.splitlines()]


def save_spec_run(spec: RunSpec[Any], logdir: Path, error: str | None = None) -> None:
    result = RunResult(
        suite_name="workspace",
        pipeline_name="openai_gpt-5.4-mini",
        model=spec.model,
        provider="OpenAI",
        finish_reasons=["stop"],
        defense=spec.defense,
        user_task_id=spec.task.id,
        injection_task_id=None,
        attack="none",
        user_task_difficulty=TaskDifficulty.EASY,
        injection_task_difficulty=None,
        injections={},
        messages=[],
        utility=None if error else True,
        security=None,
        hit_iteration_limit=False,
        usage=Usage(),
        error=error,
        temperature=0.0,
        benchmark_version="1.0.0",
        duration=1.0,
        evaluation_timestamp="2026-10-07T12:00:00Z",
    )
    save_run(result, spec.path(logdir, "workspace"))


def test_a_dry_run_of_the_main_sweep_prints_the_scale_counts_without_a_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    cli(["sweep", str(write_sweep(tmp_path)), "--dry-run"])

    assert dry_run_lines(capsys) == [
        ["utility", "total=1250", "done=0", "todo=1250"],
        ["security", "total=18750", "done=0", "todo=18750"],
        ["injection checks", "total=125", "done=0", "todo=125"],
        ["subset validation", "total=1250", "done=0", "todo=1250"],
        ["total", "total=21375", "done=0", "todo=21375"],
    ]
    assert not (tmp_path / "runs").exists()


def test_a_dry_run_of_the_weak_attacks_sweep_prints_1250_security_runs_of_attacks_the_main_sweep_does_not_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    main = yaml.safe_load(MAIN_SWEEP.read_text())
    weak = yaml.safe_load(MAIN_WEAK_ATTACKS_SWEEP.read_text())

    cli(["sweep", str(write_sweep(tmp_path, MAIN_WEAK_ATTACKS_SWEEP)), "--dry-run"])

    assert main["attacks"] == ["fake-completion", "task-aligned", "tool-notice"]
    assert weak["attacks"] == ["direct-instruction"]
    assert weak["defenses"] == ["none"]
    assert weak["logdir"] == main["logdir"]
    assert main["run_types"]["subset_validation"]["attacks"] == ["tool-notice"]
    assert dry_run_lines(capsys) == [
        ["security", "total=1250", "done=0", "todo=1250"],
        ["total", "total=1250", "done=0", "todo=1250"],
    ]


def test_a_dry_run_of_the_candidate_pilot_sweep_prints_2000_security_runs_of_the_four_attacks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    attacks = yaml.safe_load(PILOT_ATTACKS_SWEEP.read_text())["attacks"]

    cli(["sweep", str(write_sweep(tmp_path, PILOT_ATTACKS_SWEEP)), "--dry-run"])

    assert attacks == ["direct-instruction", "fake-completion", "task-aligned", "tool-notice"]
    assert dry_run_lines(capsys) == [
        ["security", "total=2000", "done=0", "todo=2000"],
        ["total", "total=2000", "done=0", "todo=2000"],
    ]


def test_a_dry_run_of_the_task_pilot_sweep_prints_250_utility_runs_and_125_injection_checks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    cli(["sweep", str(write_sweep(tmp_path, PILOT_TASKS_SWEEP)), "--dry-run"])

    assert dry_run_lines(capsys) == [
        ["utility", "total=250", "done=0", "todo=250"],
        ["injection checks", "total=125", "done=0", "todo=125"],
        ["total", "total=375", "done=0", "todo=375"],
    ]


def test_a_dry_run_of_the_defense_pilot_sweep_prints_400_utility_and_2000_security_runs_of_the_four_defenses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    sweep = yaml.safe_load(PILOT_DEFENSES_SWEEP.read_text())

    cli(["sweep", str(write_sweep(tmp_path, PILOT_DEFENSES_SWEEP)), "--dry-run"])

    assert sweep["defenses"] == ["spotlighting", "sanitizer", "tool-filter", "security-policy"]
    assert sweep["attacks"] == ["direct-instruction", "fake-completion", "task-aligned", "tool-notice"]
    assert dry_run_lines(capsys) == [
        ["utility", "total=400", "done=0", "todo=400"],
        ["security", "total=2000", "done=0", "todo=2000"],
        ["total", "total=2400", "done=0", "todo=2400"],
    ]


def test_a_dry_run_counts_only_run_files_without_an_error_as_done(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    logdir = tmp_path / "runs"
    workspace = SUITES["workspace"]
    first, second, third = (RunSpec("openai/gpt-5.4-mini", "none", task) for task in workspace.user_tasks[:3])
    save_spec_run(first, logdir)
    save_spec_run(second, logdir)
    save_spec_run(third, logdir, error="TimeoutError: no reply")
    path = write_sweep(tmp_path, run_types={"utility": {}})

    cli(["sweep", str(path), "--dry-run"])

    assert dry_run_lines(capsys) == [
        ["utility", "total=1250", "done=2", "todo=1248"],
        ["total", "total=1250", "done=2", "todo=1248"],
    ]


def test_a_dry_run_with_only_prints_those_run_types_and_their_total(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    cli(["sweep", str(write_sweep(tmp_path)), "--dry-run", "--only", "security"])

    assert dry_run_lines(capsys) == [
        ["security", "total=18750", "done=0", "todo=18750"],
        ["total", "total=18750", "done=0", "todo=18750"],
    ]


@pytest.mark.parametrize(
    ("changes", "name"),
    [
        ({"suite": "banking"}, "banking"),
        ({"models": ["openai/gpt-5.4-mni"]}, "openai/gpt-5.4-mni"),
        ({"defenses": ["firewall"]}, "firewall"),
        ({"attacks": ["jailbreak"]}, "jailbreak"),
        ({"user_tasks": ["email_user_task_99"]}, "email_user_task_99"),
        ({"injection_tasks": ["email_injection_task_99"]}, "email_injection_task_99"),
        ({"run_types": {"utilty": {}}}, "utilty"),
    ],
)
def test_a_sweep_with_an_unknown_name_exits_naming_it_without_a_key(
    changes: dict[str, Any], name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(SystemExit, match=name):
        cli(["sweep", str(write_sweep(tmp_path, **changes))])

    assert not (tmp_path / "runs").exists()


class AnsweringLLM:
    """Stands in for `LLM(model, temperature, provider=...)`: answers `Done.` to every call."""

    def __init__(self, model: str, temperature: float, *, provider: str) -> None:
        self.usage = Usage()
        self.providers: list[str] = []
        self.finish_reasons: list[str | None] = []
        self.client = self

    async def query(
        self, query: str, runtime: MCPRuntime, messages: Sequence[Message] = [], extra_args: Mapping[str, Any] = {}
    ) -> State:
        self.usage += Usage(input_tokens=100, output_tokens=10, llm_calls=1, cost=0.001)
        self.providers = ["OpenAI"]
        self.finish_reasons.append("stop")
        return query, runtime, [*messages, {"role": "assistant", "content": "Done."}], extra_args

    async def close(self) -> None:
        pass


def test_a_sweep_writes_its_run_files_and_prints_a_line_per_run_then_the_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("mcp_ipi.runner.sweep.LLM", AnsweringLLM)
    path = write_sweep(
        tmp_path,
        models=["openai/gpt-5.4-mini"],
        defenses=["none"],
        attacks=["direct-instruction"],
        user_tasks=["email_user_task_0"],
        injection_tasks=["web_injection_task_0"],
        run_types={"utility": {}, "injection_task_checks": {}, "subset_validation": {"pairs": "full"}},
        concurrency={"openai": 2},
    )

    cli(["sweep", str(path)])

    runs = "openai_gpt-5.4-mini/workspace"
    expected = [
        f"{runs}/email_user_task_0/none/none.json",
        f"{runs}/web_injection_task_0/none/none.json",
        f"{runs}/email_user_task_0/direct-instruction/web_injection_task_0.json",
    ]
    logdir = tmp_path / "runs"
    assert sorted(str(file.relative_to(logdir)) for file in logdir.rglob("*.json")) == sorted(expected)
    lines = capsys.readouterr().out.splitlines()
    assert sorted([line.split()[0], line.split()[-1]] for line in lines[:-1]) == sorted(
        ["done", file] for file in expected
    )
    assert lines[-1].startswith("3 runs, 0 errors, ")
