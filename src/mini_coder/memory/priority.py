"""Priority levels and helper functions for context management.

This module defines the priority system used to manage message importance
in the context memory system.

Priority Strategy (Improved):
- Recent messages (last N turns) have higher priority
- Older messages degrade in priority over time
- System prompts always have highest priority
- Compressible range is wider to enable actual compression
"""

from enum import IntEnum


class Priority(IntEnum):
    """Message priority levels for context management.

    Lower values indicate higher priority. Messages with higher priority
    are preserved longer in context and compressed last.

    Improved priority system:
    - CRITICAL: System prompts, never compressed
    - HIGH: Recent user input (last 2 turns)
    - MEDIUM: Recent assistant responses (last 2 turns)
    - NORMAL: Older conversation (compressible with summary)
    - LOW: Old history (compressible, keep only summary)
    - ARCHIVE: Completed tasks (compressible, may discard)
    """

    CRITICAL = 0   # System prompt, never compressed
    HIGH = 1       # Recent user input (last 2 turns)
    MEDIUM = 2     # Recent assistant responses (last 2 turns)
    NORMAL = 4     # Older conversation (3-6 turns ago)
    LOW = 6        # Old history (7+ turns ago)
    ARCHIVE = 8    # Completed tasks, very old content


def get_default_priority(role: str) -> int:
    """Get the default priority for a message based on its role.

    Note: This returns the initial priority. The priority may be
    adjusted based on message age/position in conversation.

    Args:
        role: The role of the message sender (user, assistant, system).

    Returns:
        The default priority level for the role.

    Raises:
        ValueError: If the role is not recognized.
    """
    role_priorities = {
        "system": Priority.CRITICAL,    # System prompts are critical
        "user": Priority.HIGH,          # User input starts high
        "assistant": Priority.MEDIUM,   # Assistant responses start medium
    }

    if role not in role_priorities:
        raise ValueError(f"Unknown role: {role}. Must be one of: {list(role_priorities.keys())}")

    return role_priorities[role]


def calculate_priority_by_age(
    base_priority: int,
    turns_ago: int,
    preserve_recent_turns: int = 4
) -> int:
    """Calculate priority based on message age.

    Messages degrade in priority as they get older, but recent
    messages are preserved.

    Args:
        base_priority: The initial priority based on role.
        turns_ago: How many turns ago this message was (0 = current).
        preserve_recent_turns: Number of recent turns to preserve.

    Returns:
        Adjusted priority level.
    """
    # System messages never degrade
    if base_priority == Priority.CRITICAL:
        return Priority.CRITICAL

    # Recent messages keep their priority
    if turns_ago < preserve_recent_turns:
        return base_priority

    # Older messages degrade
    if turns_ago < preserve_recent_turns + 4:
        return Priority.NORMAL  # 4-8 turns ago

    if turns_ago < preserve_recent_turns + 8:
        return Priority.LOW     # 8-12 turns ago

    return Priority.ARCHIVE     # 12+ turns ago


def is_high_priority(priority: int) -> bool:
    """Check if a priority level is considered high priority.

    High priority messages (levels 0-2) are preserved during compression.

    Args:
        priority: The priority level to check.

    Returns:
        True if the priority is high (0-2), False otherwise.
    """
    return priority <= Priority.MEDIUM


def is_compressible(priority: int) -> bool:
    """Check if a message with the given priority can be compressed.

    NORMAL, LOW, and ARCHIVE priority messages are eligible for compression.
    This wider range enables actual compression to occur.

    Args:
        priority: The priority level to check.

    Returns:
        True if the message can be compressed, False otherwise.
    """
    return priority >= Priority.NORMAL


def should_summarize(priority: int) -> bool:
    """Check if a message should be summarized rather than kept verbatim.

    LOW and ARCHIVE messages should be summarized.
    NORMAL messages can be kept or summarized depending on space.

    Args:
        priority: The priority level to check.

    Returns:
        True if the message should be summarized.
    """
    return priority >= Priority.LOW


def compare_priorities(p1: int, p2: int) -> int:
    """Compare two priority levels.

    Args:
        p1: First priority level.
        p2: Second priority level.

    Returns:
        Negative if p1 is higher priority, positive if p2 is higher,
        zero if equal.
    """
    return p1 - p2
