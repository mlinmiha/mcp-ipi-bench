"""A suite: domains composed over one environment class and its data directory, with its tasks."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from mcp_ipi.domains import Domain
from mcp_ipi.environment import load_environment, load_injection_vectors

from .task import Task

Policy = Callable[[str, dict[str, Any]], str | None]
"""A suite's policy: `(tool name, arguments) -> reason the call is forbidden, or None to allow it`."""


@dataclass(frozen=True)
class Suite[E: BaseModel]:
    """A benchmark suite: domains whose tools work on one shared environment, and the tasks run on it.

    Attributes:
        name: The suite's name, e.g. `workspace`.
        domains: The domains, in order; their tool names must be unique across domains.
        environment_cls: The environment model, with one field per domain named after its component.
        data_path: Directory with `environment.yaml` and `injection_vectors.yaml`.
        user_name: The name of the user the environment belongs to, used for attacks' `{user}`.
        user_tasks: The user tasks, in order; empty for a suite without tasks.
        injection_tasks: The injection tasks, in order; empty for a suite that only measures utility.
        security_policy: The rules of the `security-policy` defense. It is required, keyword-only, so every suite
            states its own and the defense is never silently the baseline.

    Raises:
        ValueError: Two domains have a tool with the same name.
    """

    name: str
    domains: tuple[Domain, ...]
    environment_cls: type[E]
    data_path: Path
    user_name: str = ""
    user_tasks: tuple[Task[E], ...] = ()
    injection_tasks: tuple[Task[E], ...] = ()
    security_policy: Policy = field(kw_only=True)

    def __post_init__(self) -> None:
        if len({tool.__name__ for tool in self.tools}) != len(self.tools):
            raise ValueError(f"Suite {self.name!r} has a tool name shared by two domains")

    @property
    def tools(self) -> tuple[Callable, ...]:
        """All tools of all domains, in domain order."""
        return tuple(tool for domain in self.domains for tool in domain.tools)

    def get_user_task_by_id(self, task_id: str) -> Task[E]:
        """Return the user task with this ID.

        Raises:
            KeyError: No user task has this ID.
        """
        return {task.id: task for task in self.user_tasks}[task_id]

    def get_injection_task_by_id(self, task_id: str) -> Task[E]:
        """Return the injection task with this ID.

        Raises:
            KeyError: No injection task has this ID.
        """
        return {task.id: task for task in self.injection_tasks}[task_id]

    def load_injection_defaults(self) -> dict[str, str]:
        """Load each declared injection vector's default text, keyed by vector ID."""
        vectors = load_injection_vectors(self.data_path / "injection_vectors.yaml")
        return {vector_id: vector.default for vector_id, vector in vectors.items()}

    def load_environment(self, injections: Mapping[str, str] | None = None) -> E:
        """Load a fresh environment with every injection vector at its default, except those in `injections`."""
        return load_environment(
            self.data_path / "environment.yaml",
            self.environment_cls,
            {**self.load_injection_defaults(), **(injections or {})},
        )

    def check_ground_truth(self, task: Task[E]) -> bool:
        """Run a task's ground truth on a fresh default environment and return its check on the expected answer.

        Raises:
            KeyError: A ground truth call names a tool that no domain has.
        """
        pre_environment, post_environment = self.load_environment(), self.load_environment()
        self._run_ground_truth(task, post_environment)
        return task.check(task.ground_truth_output, pre_environment, post_environment)

    def injection_vectors_read(self, task: Task[E]) -> list[str]:
        """Return the injection vectors whose text the task's ground truth reads, in declaration order.

        Every vector gets a numbered canary after its default text, the ground truth is run with the real tools, and
        a vector is read when its canary appears in a tool output. The default text stays and the canary does not
        contain the vector ID, so a search matches the same items as with the defaults alone.

        Raises:
            KeyError: A ground truth call names a tool that no domain has.
        """
        defaults = self.load_injection_defaults()
        canaries = {vector_id: f"<CANARY {index}>" for index, vector_id in enumerate(defaults)}
        injections = {vector_id: f"{defaults[vector_id]} {canary}" for vector_id, canary in canaries.items()}
        outputs = str(self._run_ground_truth(task, self.load_environment(injections)))
        return [vector_id for vector_id, canary in canaries.items() if canary in outputs]

    def _run_ground_truth(self, task: Task[E], environment: E) -> list[Any]:
        """Run the task's ground truth calls on `environment` and return what each tool returned.

        A tool that raises gets `"ErrorType: message"` as its output, as in the MCP server, and the next call
        runs.

        Raises:
            KeyError: A call names a tool that no domain has.
        """
        tools = {tool.__name__: (tool, domain.component) for domain in self.domains for tool in domain.tools}
        outputs = []
        for call in task.ground_truth():
            tool, component = tools[call.tool]
            try:
                outputs.append(tool(getattr(environment, component), **call.args))
            except Exception as exc:
                outputs.append(f"{type(exc).__name__}: {exc}")
        return outputs
