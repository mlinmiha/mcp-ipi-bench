"""A live `ipi benchmark` security run with the real OpenRouter model."""

from pathlib import Path

import pytest

from mcp_ipi.cli import cli
from mcp_ipi.runner import load_run

pytestmark = pytest.mark.live


def test_benchmark_writes_a_security_run_file(tmp_path: Path):
    cli(
        [
            "benchmark",
            "--model",
            "openai/gpt-5.4-mini",
            "--attack",
            "direct-instruction",
            "-ut",
            "email_user_task_0",
            "-it",
            "web_injection_task_0",
            "--logdir",
            str(tmp_path),
        ]
    )

    path = tmp_path / "openai_gpt-5.4-mini/workspace/email_user_task_0/direct-instruction/web_injection_task_0.json"
    run = load_run(path)
    assert run.error is None, run.error
    assert isinstance(run.security, bool)
    assert run.usage.llm_calls >= 1
    assert run.usage.input_tokens > 0
    assert run.usage.output_tokens > 0
    assert run.usage.cost is not None and run.usage.cost > 0
    assert run.provider
