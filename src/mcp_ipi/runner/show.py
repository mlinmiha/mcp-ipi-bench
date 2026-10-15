"""Readable views of run files for the terminal: one run with every model call and tool execution (`format_run`), a table of runs (`format_table`) and
the summary line of runs (`format_summary`)."""

from mcp_ipi.agent import Message

from .run_file import RunResult

SECTION_WIDTH = 56
WRAP_WIDTH = 100
"""How many characters of a recorded line are shown on one terminal line before it wraps."""


def format_run(result: RunResult) -> str:
    """Show a run as its model calls and tool executions in order, then a summary of the run.

    Each `MODEL CALL #n` section shows every message the model was sent, then the assistant message it returned. Each
    `TOOL EXECUTION #n` section shows the tool's name and its result. Recorded text is shown verbatim, each line after
    a `│ ` gutter; a tool call shows the tool's name and its raw arguments string in a gutter of its own.
    """
    sections: list[list[str]] = []
    names = {
        call["id"]: call["function"]["name"]
        for message in result.messages
        if message["role"] == "assistant"
        for call in message.get("tool_calls", [])
    }
    model_calls = tool_executions = 0
    for index, message in enumerate(result.messages):
        if message["role"] == "assistant":
            model_calls += 1
            lines = [_section(f"MODEL CALL #{model_calls}"), ""]
            for sent in result.messages[: index + 1]:
                lines += [*_format_message(sent), ""]
            sections.append(lines)
        elif message["role"] == "tool":
            tool_executions += 1
            sections.append(
                [
                    _section(f"TOOL EXECUTION #{tool_executions}"),
                    "",
                    "TOOL",
                    *_gutter(names[message["tool_call_id"]]),
                    "",
                    "RESULT",
                    *_gutter(message["content"]),
                    "",
                ]
            )
    provider = ", ".join(result.provider) if isinstance(result.provider, list) else result.provider or "?"
    fields = {
        "suite": result.suite_name,
        "user task": result.user_task_id,
        "injection task": result.injection_task_id or "none",
        "model": result.model,
        "provider": provider,
        "defense": result.defense,
        "attack": result.attack,
        "model calls": result.usage.llm_calls,
        "tool executions": tool_executions,
        "input tokens": result.usage.input_tokens,
        "output tokens": result.usage.output_tokens,
        "cost": format_cost(result.usage.cost),
        "duration": f"{result.duration:.1f}s",
        "utility": str(result.utility).lower(),
        "security": str(result.security).lower(),
        "hit iteration limit": str(result.hit_iteration_limit).lower(),
    }
    if result.error:
        fields["error"] = result.error
    sections.append([_section("RUN"), "", *(f"  {key + ':':<21}{value}" for key, value in fields.items())])
    return "\n\n".join("\n".join(lines) for lines in sections)


def format_table(results: list[RunResult]) -> str:
    """Show runs as a table, one row per run: task, model, utility, security, calls, cost and duration.

    The task is the user task, plus ` + <injection task> (<attack>)` for a security run; utility is `error` for a run
    with an error. Each column is as wide as its longest cell.
    """
    rows = [["task", "model", "utility", "security", "calls", "cost", "time"]]
    for result in results:
        task = result.user_task_id
        if result.attack != "none":
            task += f" + {result.injection_task_id} ({result.attack})"
        rows.append(
            [
                task,
                result.model,
                "error" if result.error else str(result.utility),
                str(result.security),
                str(result.usage.llm_calls),
                format_cost(result.usage.cost),
                f"{result.duration:.1f}s",
            ]
        )
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip() for row in rows
    )


def format_summary(results: list[RunResult]) -> str:
    """Summarize runs in one line: the number of runs and errors, utility and, for security runs, the ASR, then cost.

    Utility is counted over the runs without errors, and the ASR over those of them that are security runs (`attack`
    is not `"none"`), e.g. `4 runs, 1 errors, utility 2/3, ASR 1/2, cost $0.0123`; each is left out without such runs.
    The cost sums the runs whose cost is known, error runs included, and says how many runs have none, e.g. ` (1 runs
    without cost)`.
    """
    scored = [result for result in results if result.error is None]
    summary = f"{len(results)} runs, {len(results) - len(scored)} errors"
    if scored:
        utility = sum(result.utility is True for result in scored)
        summary += f", utility {utility}/{len(scored)}"
        attacked = [result for result in scored if result.attack != "none"]
        if attacked:
            security = sum(result.security is True for result in attacked)
            summary += f", ASR {security}/{len(attacked)}"
    costs = [result.usage.cost for result in results if result.usage.cost is not None]
    summary += f", cost ${sum(costs):.4f}"
    if len(costs) < len(results):
        summary += f" ({len(results) - len(costs)} runs without cost)"
    return summary


def format_cost(cost: float | None) -> str:
    """Write a cost in USD to 4 decimals, or `$?` when it is unknown."""
    return "$?" if cost is None else f"${cost:.4f}"


def _format_message(message: Message) -> list[str]:
    """Show a message as its role and its content in a gutter, with an assistant's tool calls after its text."""
    lines = [message["role"].upper(), *_gutter(message["content"] or "")]
    if message["role"] == "assistant":
        for call in message.get("tool_calls", []):
            lines += [
                "│",
                "│ TOOL CALL",
                *_gutter(call["function"]["name"], prefix="│ │"),
                *_gutter(call["function"]["arguments"], prefix="│ │", empty="[no arguments]"),
            ]
    return lines


def _gutter(text: str, prefix: str = "│", empty: str = "[no text]") -> list[str]:
    """Put each line of a text after the gutter `prefix`, or `empty` when the text is empty.

    A line longer than `WRAP_WIDTH` wraps after its last space that fits (or at `WRAP_WIDTH` if none does), and each
    wrapped piece goes after the gutter with its last `│` dotted (`┆`), so it is not taken for a new line.
    """
    lines = []
    for line in text.split("\n") if text else [empty]:
        gutter = prefix
        while len(line) > WRAP_WIDTH:
            cut = line.rfind(" ", 0, WRAP_WIDTH) + 1 or WRAP_WIDTH
            lines.append(f"{gutter} {line[:cut]}".rstrip())
            gutter, line = f"{prefix[:-1]}┆", line[cut:]
        lines.append(f"{gutter} {line}".rstrip())
    return lines


def _section(title: str) -> str:
    return f" {title} ".center(SECTION_WIDTH, "━")
