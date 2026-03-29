"""
PawPal+ — Logic Layer
Core classes for managing pet care tasks and generating a daily schedule.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------

@dataclass
class Owner:
    """Stores owner profile and the daily time constraint for scheduling."""

    name: str
    available_minutes_per_day: int


# ---------------------------------------------------------------------------
# Pet
# ---------------------------------------------------------------------------

@dataclass
class Pet:
    """Stores pet profile and care context used to inform scheduling decisions."""

    name: str
    species: str
    age: int
    special_needs: str


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """
    Represents one care task (e.g. feeding, walk, medication, grooming).

    priority must be one of: 'high', 'medium', 'low'.
    mandatory tasks are scheduled regardless of available time.
    """

    name: str
    category: str
    duration_minutes: int
    priority: str        # TODO: validate — must be "high", "medium", or "low"
    completed: bool = False
    mandatory: bool = False

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        # TODO: raise an error or warn if already completed
        self.completed = True


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    """
    Core scheduling engine. Coordinates Owner, Pet, and Task objects to
    produce a prioritized daily care plan within the owner's time constraint.

    Input:  Owner (time limit), Pet (care context), list of Tasks
    Output: filtered, ordered list of Tasks that fit within available time
    """

    def __init__(self, owner: Owner, pet: Pet) -> None:
        self.owner: Owner = owner
        self.pet: Pet = pet
        self.tasks: list[Task] = []

    def add_task(self, task: Task) -> None:
        """
        Add a task to the scheduler's task list.

        TODO: reject tasks with duration_minutes <= 0
        TODO: reject duplicate task names (case-insensitive)
        """
        pass

    def remove_task(self, task_name: str) -> None:
        """
        Remove a task by name from the task list.

        TODO: handle case where task_name does not exist
        """
        pass

    def generate_plan(self) -> list[Task]:
        """
        Return an ordered list of tasks that fit within available_minutes_per_day.

        Scheduling rules (to implement):
          1. Always include mandatory tasks first, regardless of time.
          2. Fill remaining time with non-mandatory tasks sorted by priority
             (high → medium → low).
          3. Skip completed tasks.
          4. Stop adding tasks once available time is exhausted.

        Edge cases to handle:
          - No tasks → return []
          - Zero available time → return mandatory tasks only
          - All tasks exceed available time → return mandatory tasks only
          - All tasks already completed → return []
        """
        return []

    def explain_plan(self) -> str:
        """
        Return a human-readable explanation of why tasks were included or skipped.

        Calls generate_plan() internally and compares result against full task list.
        Returns a formatted string summarising scheduled vs. skipped tasks and reasons.
        """
        return ""
