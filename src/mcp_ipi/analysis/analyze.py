"""`analyze`: from the run files of a logdir to the CSV files of the tables, and the tables as text."""

import csv
from pathlib import Path

from .runs import load_runs
from .tables import (
    POOLED_GRAINS,
    Table,
    cost_table,
    difficulty_table,
    domains_table,
    errors_table,
    h1_attack_pairs_table,
    h1_attacks_table,
    h2_defenses_by_attack_table,
    h2_defenses_table,
    h3_breadth_table,
    h3_coverage_table,
    h3_injection_tasks_table,
    h3_levels_table,
    injection_checks_table,
    paired_table,
    pooled_security_table,
    security_table,
    subset_validation_table,
    utility_table,
)


def analyze(logdir: Path, out: Path) -> list[Table]:
    """Compute every table from the run files under the logdir and write each to `<out>/<name>.csv`.

    The output directory is created if missing and its files are overwritten; a table without rows is written with
    its header only.

    Raises:
        NoRunFilesError: The logdir holds no run file; nothing is written.
    """
    database = load_runs(logdir)
    tables = [
        utility_table(database),
        security_table(database),
        *(pooled_security_table(database, grain) for grain in POOLED_GRAINS),
        domains_table(database),
        difficulty_table(database),
        injection_checks_table(database),
        paired_table(database),
        cost_table(database),
        subset_validation_table(database),
        errors_table(database),
        h1_attacks_table(database),
        h1_attack_pairs_table(database),
        h2_defenses_table(database),
        h2_defenses_by_attack_table(database),
        h3_coverage_table(database),
        h3_levels_table(database),
        h3_injection_tasks_table(database),
        h3_breadth_table(database),
    ]
    out.mkdir(parents=True, exist_ok=True)
    for table in tables:
        with (out / f"{table.name}.csv").open("w", newline="") as file:
            csv.writer(file, lineterminator="\n").writerows([table.header, *table.rows])
    return tables


def format_tables(tables: list[Table]) -> str:
    """Show the tables one after another, with an empty line between them.

    Each is its title line `<name>: <title>`, its header and its rows, with every column as wide as its longest cell.
    """
    texts = []
    for table in tables:
        rows = [table.header, *table.rows]
        widths = [max(len(row[column]) for row in rows) for column in range(len(table.header))]
        lines = ["  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip() for row in rows]
        texts.append("\n".join([f"{table.name}: {table.title}", *lines]))
    return "\n\n".join(texts)
