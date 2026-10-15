"""The balanced subset of user task and injection task pairs that security runs use."""

from collections.abc import Sequence

from .task import Task


def balanced_pairs[T: Task](user_tasks: Sequence[T], injection_tasks: Sequence[T]) -> list[tuple[T, T]]:
    """Pair the k-th user task of each source domain with injection task `k mod n` of every target domain.

    `k` is the user task's position within its domain and `n` the number of injection tasks in the target domain,
    both in the given order. The source domain is the user task's `domain`, the target domain the injection task's.
    """
    by_domain: dict[str, list[T]] = {}
    for task in injection_tasks:
        by_domain.setdefault(task.domain, []).append(task)
    seen: dict[str, int] = {}
    pairs = []
    for user_task in user_tasks:
        k = seen.get(user_task.domain, 0)
        seen[user_task.domain] = k + 1
        pairs += [(user_task, tasks[k % len(tasks)]) for tasks in by_domain.values()]
    return pairs
