"""The checks of `ipi check-suite`: is a suite sound enough to run, without any model call."""

from collections import Counter

from mcp_ipi.environment import find_injection_placeholders, load_yaml

from .pairing import balanced_pairs
from .suite import Suite


def check_suite(suite: Suite) -> list[str]:
    """Return the problems found in `suite`, one string each starting with the task or vector ID it is about.

    In order: every task's ground truth passes its check on a fresh environment; every task's domain is a suite
    domain; every user task reads an injection vector of its own domain; the environment's placeholders are exactly
    the declared injection vectors; and in the balanced pairs every user task is paired once with each target domain
    and every injection task is used equally often. Tool names are unique already, or the suite could not be built.
    A placeholder without a declared vector is the only problem returned, since no environment can be loaded then.
    """
    declared = suite.load_injection_defaults()
    placed = find_injection_placeholders(load_yaml(suite.data_path / "environment.yaml"))
    undeclared = [vector_id for vector_id in dict.fromkeys(placed) if vector_id not in declared]
    if undeclared:
        return [f"{vector_id}: has a placeholder but is not declared" for vector_id in undeclared]

    problems = []
    for task in suite.user_tasks + suite.injection_tasks:
        try:
            if not suite.check_ground_truth(task):
                problems.append(f"{task.id}: ground truth does not pass its check")
        except KeyError as error:
            problems.append(f"{task.id}: ground truth raised KeyError {error}")

    domains = {domain.name for domain in suite.domains}
    for task in suite.user_tasks + suite.injection_tasks:
        if task.domain not in domains:
            problems.append(f"{task.id}: domain {task.domain!r} is not a domain of the suite")

    for task in suite.user_tasks:
        try:
            vectors = suite.injection_vectors_read(task)
        except KeyError:
            continue  # its ground truth already raised above
        if not any(vector_id.startswith(f"{task.domain}_") for vector_id in vectors):
            problems.append(f"{task.id}: reads no injection vector of its domain {task.domain!r}")

    problems += [f"{vector_id}: declared but has no placeholder" for vector_id in declared if vector_id not in placed]

    pairs = balanced_pairs(suite.user_tasks, suite.injection_tasks)
    targets = dict.fromkeys(task.domain for task in suite.injection_tasks)
    per_target = Counter((user_task.id, injection_task.domain) for user_task, injection_task in pairs)
    for task in suite.user_tasks:
        for target in targets:
            if per_target[task.id, target] != 1:
                problems.append(f"{task.id}: paired {per_target[task.id, target]} times with target domain {target!r}")
    uses = Counter(injection_task.id for _, injection_task in pairs)
    fewest = min((uses[task.id] for task in suite.injection_tasks), default=0)
    problems += [
        f"{task.id}: used in {uses[task.id]} pairs, the fewest is {fewest}"
        for task in suite.injection_tasks
        if uses[task.id] != fewest
    ]
    return problems
