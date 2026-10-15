"""Entry point for the ipi command-line tool."""

import argparse
import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from mcp_ipi.analysis import NoRunFilesError, analyze, format_tables
from mcp_ipi.attacks import ATTACKS
from mcp_ipi.defenses import DEFENSES
from mcp_ipi.runner import (
    MODEL_NAMES,
    RUN_TYPES,
    RunSpec,
    RunTypeName,
    benchmark_model,
    expand_sweep,
    format_dry_run,
    format_run,
    format_summary,
    format_table,
    load_run,
    load_sweep,
    sweep_runs,
)
from mcp_ipi.suites import SUITES, balanced_pairs, check_suite


def cli(argv: Sequence[str] | None = None) -> None:
    """Parse the command line and run its subcommand."""
    args = build_parser().parse_args(argv)
    if args.command == "benchmark":
        run_benchmark(args)
    elif args.command == "check-suite":
        run_check_suite(args)
    elif args.command == "sweep":
        run_sweep(args)
    elif args.command == "analyze":
        run_analyze(args)
    else:
        run_show(args)


def run_benchmark(args: argparse.Namespace) -> None:
    """Run `ipi benchmark`: its runs print one line each as they go, then the summary line of them all.

    Raises:
        SystemExit: A task ID is unknown; raised before the model is built.
    """
    suite = SUITES[args.suite]
    try:
        user_tasks = [suite.get_user_task_by_id(task_id) for task_id in args.user_task] or suite.user_tasks
        injection_tasks = [
            suite.get_injection_task_by_id(task_id) for task_id in args.injection_task
        ] or suite.injection_tasks
    except KeyError as error:
        raise SystemExit(f"ipi benchmark: unknown task ID {error}") from None

    # The openai SDK's HTTP client logs every request under `httpx2`; one line per run is enough.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    results = asyncio.run(
        benchmark_model(
            suite,
            model=args.model,
            defense=args.defense,
            attack=ATTACKS[args.attack] if args.attack else None,
            user_tasks=user_tasks,
            injection_tasks=injection_tasks,
            pairs=args.pairs,
            injection_task_checks=args.injection_task_checks,
            max_workers=args.max_workers,
            temperature=args.temperature,
            logdir=args.logdir,
            force_rerun=args.force_rerun,
        )
    )
    print(format_summary(results))


def run_check_suite(args: argparse.Namespace) -> None:
    """Print each problem `check_suite` finds in the suite, or one line with its task and pair counts if none.

    Raises:
        SystemExit: The suite has a problem; the status is 1.
    """
    suite = SUITES[args.suite]
    problems = check_suite(suite)
    if problems:
        print("\n".join(problems))
        raise SystemExit(1)
    pairs = balanced_pairs(suite.user_tasks, suite.injection_tasks)
    print(
        f"{suite.name}: {len(suite.user_tasks)} user tasks, {len(suite.injection_tasks)} injection tasks, "
        f"{len(pairs)} pairs OK"
    )


def run_sweep(args: argparse.Namespace) -> None:
    """Run `ipi sweep`: its runs print one line each as they go, then the summary line of them all; with `--dry-run`,
    print the runs per run type in total, done and to do, and their total, instead.

    Raises:
        SystemExit: The file is not a sweep file (e.g. an unknown run type), or the sweep's suite, a model, defense,
            attack or task ID is unknown; raised before any model is built.
    """
    try:
        sweep = load_sweep(args.file)
    except ValidationError as error:
        raise SystemExit(f"ipi sweep: {args.file} is not a sweep file: {error}") from None
    try:
        suite = SUITES[sweep.suite]
        expanded: dict[RunTypeName, list[RunSpec]] = {
            name: specs for name, specs in expand_sweep(suite, sweep).items() if not args.only or name in args.only
        }
    except KeyError as error:
        raise SystemExit(f"ipi sweep: unknown name {error}") from None
    if args.dry_run:
        print(format_dry_run(expanded, sweep.logdir, suite.name))
        return

    # The openai SDK's HTTP client logs every request under `httpx2`; one line per run is enough.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    specs = [spec for run_type_specs in expanded.values() for spec in run_type_specs]
    results = asyncio.run(
        sweep_runs(
            suite,
            specs,
            temperature=sweep.temperature,
            logdir=sweep.logdir,
            force_rerun=args.force_rerun,
            concurrency=sweep.concurrency,
        )
    )
    print(format_summary(results))


def run_analyze(args: argparse.Namespace) -> None:
    """Run `ipi analyze`: write the tables of the logdir's run files as CSV files to the output directory and print them.

    Raises:
        SystemExit: The logdir holds no run file.
    """
    try:
        tables = analyze(args.logdir, args.out or args.logdir / "analysis")
    except NoRunFilesError:
        raise SystemExit(f"ipi analyze: no run files under {args.logdir}") from None
    print(format_tables(tables))


def run_show(args: argparse.Namespace) -> None:
    """Print each run file readably, one after another, or with `--summary` one table of them and the summary line."""
    results = [load_run(path) for path in args.files]
    if args.summary:
        print(format_table(results))
        print(format_summary(results))
        return
    print("\n\n".join(format_run(result) for result in results))


def build_parser() -> argparse.ArgumentParser:
    """Build the parser of `ipi` and its subcommands."""
    parser = argparse.ArgumentParser(prog="ipi")
    commands = parser.add_subparsers(dest="command", required=True)

    # benchmark
    benchmark_parser = commands.add_parser(
        "benchmark", help="run one pipeline (a model/defense combination) and write its run files"
    )
    benchmark_parser.add_argument("--model", required=True, choices=MODEL_NAMES, help="OpenRouter model ID")
    benchmark_parser.add_argument("--suite", default="workspace", choices=SUITES)
    benchmark_parser.add_argument("--defense", default="none", choices=DEFENSES)
    benchmark_parser.add_argument("--attack", choices=ATTACKS, help="do security runs with this attack")
    benchmark_parser.add_argument(
        "-ut", "--user-task", action="append", default=[], help="user task ID (repeatable); default all"
    )
    benchmark_parser.add_argument(
        "-it", "--injection-task", action="append", default=[], help="injection task ID (repeatable); default all"
    )
    benchmark_parser.add_argument(
        "--pairs",
        default="subset",
        choices=["subset", "full"],
        help="security runs over the balanced subset narrowed by -ut/-it, or every user task x injection task",
    )
    benchmark_parser.add_argument(
        "--injection-task-checks", action="store_true", help="run each injection task's goal as the user prompt"
    )
    benchmark_parser.add_argument(
        "--max-workers", type=int, default=1, help="runs at once, each worker with its own model object"
    )
    benchmark_parser.add_argument("--temperature", type=float, default=0.0)
    benchmark_parser.add_argument("--logdir", type=Path, default=Path("runs"))
    benchmark_parser.add_argument(
        "-f", "--force-rerun", action="store_true", help="run again even runs that are complete"
    )

    # check-suite
    check_parser = commands.add_parser("check-suite", help="check a suite is ready to run, without any model call")
    check_parser.add_argument("--suite", default="workspace", choices=SUITES)

    # sweep
    sweep_parser = commands.add_parser("sweep", help="do the runs of a sweep file: the full experiment")
    sweep_parser.add_argument("file", type=Path, help="sweep file")
    sweep_parser.add_argument(
        "--dry-run", action="store_true", help="print the runs per run type in total, done and to do; run nothing"
    )
    sweep_parser.add_argument("--only", nargs="+", choices=RUN_TYPES, help="only these run types")
    sweep_parser.add_argument("-f", "--force-rerun", action="store_true", help="run again even runs that are complete")

    # analyze
    analyze_parser = commands.add_parser("analyze", help="compute the tables from the run files; no model call")
    analyze_parser.add_argument("--logdir", type=Path, default=Path("runs"))
    analyze_parser.add_argument("--out", type=Path, help="directory of the CSV files; default <logdir>/analysis")

    # show
    show_parser = commands.add_parser("show", help="print run files readably")
    show_parser.add_argument("files", nargs="+", type=Path, help="run files")
    show_parser.add_argument("--summary", action="store_true", help="one table row per run and the summary line")
    return parser
