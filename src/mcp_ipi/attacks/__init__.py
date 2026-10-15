"""Attacks that turn an injection task's goal into attack text."""

from .base import Attack
from .direct_instruction import DIRECT_INSTRUCTION
from .fake_completion import FAKE_COMPLETION
from .task_aligned import TASK_ALIGNED
from .tool_notice import TOOL_NOTICE

ATTACKS: dict[str, Attack] = {
    attack.name: attack
    for attack in (
        DIRECT_INSTRUCTION,
        FAKE_COMPLETION,
        TASK_ALIGNED,
        TOOL_NOTICE,
    )
}
"""Each attack by its name."""

__all__ = [
    "ATTACKS",
    "DIRECT_INSTRUCTION",
    "FAKE_COMPLETION",
    "TASK_ALIGNED",
    "TOOL_NOTICE",
    "Attack",
]
