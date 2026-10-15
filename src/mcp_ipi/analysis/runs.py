"""The runs table: every run file under a logdir as one row of an in-memory DuckDB table, with derived columns."""

import json
from pathlib import Path

import duckdb

from mcp_ipi.suites import SUITES

from .coverage import COVERS

RUN_FILE_GLOB = "*/*/*/*/*.json"
"""Where the run files are under a logdir: `<pipeline>/<suite>/<user_task>/<attack>/<injection_task>.json`."""

COLUMNS = {
    "pipeline_name": "VARCHAR",
    "model": "VARCHAR",
    "defense": "VARCHAR",
    "user_task_id": "VARCHAR",
    "injection_task_id": "VARCHAR",
    "attack": "VARCHAR",
    "user_task_difficulty": "VARCHAR",
    "injection_task_difficulty": "VARCHAR",
    "utility": "BOOLEAN",
    "security": "BOOLEAN",
    "hit_iteration_limit": "BOOLEAN",
    "usage": "STRUCT(input_tokens BIGINT, output_tokens BIGINT, llm_calls BIGINT, cost DOUBLE)",
    "error": "VARCHAR",
    "duration": "DOUBLE",
    "injections": "MAP(VARCHAR, VARCHAR)",
    "messages": "STRUCT(role VARCHAR, content VARCHAR)[]",
}
"""The run file fields read from a run file. `injections` and `messages` only give the derived columns `exposed` and
`blocked` and are not kept in the runs table."""

BLOCKED_PREFIX = "PermissionError: Blocked by the security policy"
"""How the content of a tool message starts when the security policy blocked its call."""

DOMAIN_PATTERN = r"'^(.*)_(?:user|injection)_task_\d+$'"
"""SQL literal of the regular expression whose group is the domain prefix of a task ID."""

INDEX_PATTERN = r"'_(\d+)$'"
"""SQL literal of the regular expression whose group is the trailing index of a task ID."""

COVERAGE_COLUMNS = {defense: f"covered_by_{defense.replace('-', '_')}" for defense in COVERS}
"""The column of the runs table that says whether a run's pair is covered by each action-level defense."""


class NoRunFilesError(Exception):
    """The logdir holds no run file."""


def load_runs(logdir: Path) -> duckdb.DuckDBPyConnection:
    """Read every run file under the logdir into the table `runs` of a new in-memory database.

    Besides the fields of `COLUMNS`, a row has the run's `run_type` (`security` when it has an attack,
    `injection_task_check` when its user task ID is an injection task ID, `utility` otherwise), its `source_domain`
    and `target_domain` (the domain prefix of the user task ID and of the injection task ID) and the trailing
    `user_task_index` and `injection_task_index` of the two IDs. Two more are true only for a security run:
    `in_subset` when its pair is in the balanced subset (the injection task index is the user task index mod 5), and
    `compatible` when its target domain is not `email` and differs from its source domain. `capable` says for a
    security run whether its model achieved the goal of its injection task in the injection task check, and is null
    for any other run and for a model without injection task checks. `exposed` is true for a security run with a
    value of its `injections` verbatim in the content of a tool message, which is what the model saw, and `blocked`
    for a run with a tool message that starts with `BLOCKED_PREFIX`. Each column of `COVERAGE_COLUMNS` says for a
    security run whether its pair is covered by that defense, by the rule of `COVERS` on the tasks of the run's
    `suite`, the one named in the run file's path; it is null for any other run. The run files are only read.

    Raises:
        NoRunFilesError: No file under the logdir matches `RUN_FILE_GLOB`.
    """
    if not any(logdir.glob(RUN_FILE_GLOB)):
        raise NoRunFilesError(logdir)
    database = duckdb.connect()
    columns = ", ".join(f"{name}: '{sql_type}'" for name, sql_type in COLUMNS.items())
    pair_columns = {"suite": "VARCHAR", "user_task_id": "VARCHAR", "injection_task_id": "VARCHAR"}
    pairs = [
        {"suite": suite.name, "user_task_id": user_task.id, "injection_task_id": injection_task.id}
        | {column: COVERS[defense](suite, user_task, injection_task) for defense, column in COVERAGE_COLUMNS.items()}
        for suite in SUITES.values()
        for user_task in suite.user_tasks
        for injection_task in suite.injection_tasks
    ]
    database.execute(
        f"""
        CREATE TABLE runs AS
        WITH files AS (
            SELECT
                * EXCLUDE (filename),
                parse_path(filename)[-4] AS suite,
                CASE
                    WHEN attack != 'none' THEN 'security'
                    WHEN user_task_id LIKE '%injection_task%' THEN 'injection_task_check'
                    ELSE 'utility'
                END AS run_type,
                regexp_extract(user_task_id, {DOMAIN_PATTERN}, 1) AS source_domain,
                regexp_extract(injection_task_id, {DOMAIN_PATTERN}, 1) AS target_domain,
                regexp_extract(user_task_id, {INDEX_PATTERN}, 1)::INTEGER AS user_task_index,
                regexp_extract(injection_task_id, {INDEX_PATTERN}, 1)::INTEGER AS injection_task_index,
                run_type = 'security' AND injection_task_index = user_task_index % 5 AS in_subset,
                run_type = 'security' AND target_domain != 'email' AND target_domain != source_domain AS compatible,
                list_filter(messages, message -> message.role = 'tool') AS tool_messages,
                run_type = 'security' AND list_bool_or(
                    list_transform(
                        tool_messages,
                        message -> list_bool_or(
                            list_transform(map_values(injections), text -> contains(message.content, text))
                        )
                    )
                ) IS TRUE AS exposed,
                list_bool_or(
                    list_transform(tool_messages, message -> starts_with(message.content, '{BLOCKED_PREFIX}'))
                ) IS TRUE AS blocked
            FROM read_json(?, columns = {{{columns}}}, filename = true)
        ),
        checks AS (
            SELECT model, user_task_id AS injection_task_id, utility AS achieved
            FROM files
            WHERE run_type = 'injection_task_check'
        ),
        covered AS (
            SELECT unnest(from_json(?, ?), recursive := true)
        )
        SELECT
            files.* EXCLUDE (injections, messages, tool_messages),
            CASE
                WHEN run_type = 'security' AND model IN (SELECT model FROM checks) THEN coalesce(achieved, false)
            END AS capable,
            covered.* EXCLUDE ({", ".join(pair_columns)})
        FROM files
        LEFT JOIN checks USING (model, injection_task_id)
        LEFT JOIN covered USING ({", ".join(pair_columns)})
        """,
        [
            str(logdir / RUN_FILE_GLOB),
            json.dumps(pairs),
            json.dumps([pair_columns | dict.fromkeys(COVERAGE_COLUMNS.values(), "BOOLEAN")]),
        ],
    )
    return database
