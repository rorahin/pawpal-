"""
PawPal+ — Logic Layer
Core classes for managing pet care tasks and generating a daily schedule.

Ownership hierarchy:
    Owner  →  (many) Pet  →  (many) Task

The Scheduler takes an Owner and iterates Owner → Pets → Tasks to produce
a prioritized daily care plan within the owner's available time.
"""

from dataclasses import dataclass, field

# Maps priority labels to sort order (lower number = higher priority).
# Used by Scheduler.generate_plan() to rank non-mandatory tasks.
PRIORITY_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2}

_VALID_PRIORITIES: frozenset[str] = frozenset(PRIORITY_ORDER.keys())


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """
    Represents one care task (e.g. feeding, walk, medication, grooming).

    Validation (enforced in __post_init__):
      - priority must be one of: 'high', 'medium', 'low'
      - duration_minutes must be > 0

    mandatory tasks are always included in the schedule regardless of time.
    """

    name: str
    category: str
    duration_minutes: int
    priority: str
    completed: bool = False
    mandatory: bool = False

    def __post_init__(self) -> None:
        """Validate fields at construction time."""
        if self.priority not in _VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority '{self.priority}'. "
                f"Must be one of: {sorted(_VALID_PRIORITIES)}."
            )
        if self.duration_minutes <= 0:
            raise ValueError(
                f"duration_minutes must be > 0, got {self.duration_minutes}."
            )

    def mark_complete(self) -> None:
        """Mark this task as completed; raises RuntimeError if already complete."""
        if self.completed:
            raise RuntimeError(
                f"Task '{self.name}' is already marked as completed."
            )
        self.completed = True


# ---------------------------------------------------------------------------
# Pet
# ---------------------------------------------------------------------------

@dataclass
class Pet:
    """
    Stores pet profile and owns the list of care tasks associated with this pet.

    Tasks are managed through add_task() and remove_task() to enforce validation.
    Direct mutation of the tasks list bypasses duplicate checking — avoid it.
    """

    name: str
    species: str
    age: int
    special_needs: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Append task to this pet's list; raises ValueError on duplicate name (case-insensitive)."""
        task_name_lower = task.name.strip().lower()
        for existing in self.tasks:
            if existing.name.strip().lower() == task_name_lower:
                raise ValueError(
                    f"Task '{task.name}' already exists for pet '{self.name}' "
                    f"(duplicate names are not allowed, case-insensitive)."
                )
        self.tasks.append(task)

    def remove_task(self, task_name: str) -> None:
        """Remove a task by name (case-insensitive); raises ValueError if not found."""
        name_lower = task_name.strip().lower()
        for i, task in enumerate(self.tasks):
            if task.name.strip().lower() == name_lower:
                self.tasks.pop(i)
                return
        raise ValueError(
            f"No task named '{task_name}' found for pet '{self.name}'."
        )


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------

@dataclass
class Owner:
    """
    Stores owner profile, daily time constraint, and the list of owned pets.

    Pets are managed through add_pet() and remove_pet() to enforce validation.
    Direct mutation of the pets list bypasses duplicate checking — avoid it.
    """

    name: str
    available_minutes_per_day: int
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Append pet to this owner's list; raises ValueError on duplicate name (case-insensitive)."""
        pet_name_lower = pet.name.strip().lower()
        for existing in self.pets:
            if existing.name.strip().lower() == pet_name_lower:
                raise ValueError(
                    f"A pet named '{pet.name}' already exists for owner '{self.name}' "
                    f"(duplicate names are not allowed, case-insensitive)."
                )
        self.pets.append(pet)

    def remove_pet(self, pet_name: str) -> None:
        """Remove a pet by name (case-insensitive); raises ValueError if not found."""
        name_lower = pet_name.strip().lower()
        for i, pet in enumerate(self.pets):
            if pet.name.strip().lower() == name_lower:
                self.pets.pop(i)
                return
        raise ValueError(
            f"No pet named '{pet_name}' found for owner '{self.name}'."
        )


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    """
    Core scheduling engine. Takes an Owner and iterates Owner → Pets → Tasks
    to produce a prioritized daily care plan within the owner's time constraint.

    Scheduling rules:
      1. Mandatory tasks are always included, regardless of available time.
      2. Remaining time is filled with non-mandatory tasks sorted by priority
         (high → medium → low).
      3. Completed tasks are never included.
      4. Task addition stops once available time is exhausted.

    Note: if mandatory tasks collectively exceed available_minutes_per_day,
    the returned plan will exceed the time limit. Mandatory tasks cannot be
    dropped — explain_plan() will surface this condition explicitly.
    """

    def __init__(self, owner: Owner) -> None:
        """Initialize the scheduler with the Owner whose pets and tasks will be scheduled."""
        self.owner: Owner = owner

    def _collect_all_tasks(self) -> list[tuple[Pet, Task]]:
        """Flatten owner → pets → tasks into a list of (Pet, Task) tuples."""
        result: list[tuple[Pet, Task]] = []
        for pet in self.owner.pets:
            for task in pet.tasks:
                result.append((pet, task))
        return result

    def generate_plan(self) -> list[Task]:
        """
        Return an ordered list of tasks that fit within available_minutes_per_day.

        Mandatory tasks are always included first. Remaining capacity is filled
        with non-mandatory tasks in priority order (high → medium → low).
        Completed tasks are always skipped.

        Returns:
            Ordered list of Task objects to execute today.
        """
        all_pairs = self._collect_all_tasks()

        if not all_pairs:
            return []

        mandatory: list[Task] = []
        non_mandatory: list[Task] = []

        for _pet, task in all_pairs:
            if task.completed:
                continue
            if task.mandatory:
                mandatory.append(task)
            else:
                non_mandatory.append(task)

        # Sort non-mandatory by priority order, then by name for stable deterministic output.
        non_mandatory.sort(key=lambda t: (PRIORITY_ORDER[t.priority], t.name.lower()))

        plan: list[Task] = list(mandatory)  # mandatory tasks always included

        mandatory_minutes = sum(t.duration_minutes for t in mandatory)
        remaining_minutes = self.owner.available_minutes_per_day - mandatory_minutes

        for task in non_mandatory:
            if remaining_minutes <= 0:
                break
            if task.duration_minutes <= remaining_minutes:
                plan.append(task)
                remaining_minutes -= task.duration_minutes

        return plan

    def explain_plan(self, plan: list[Task] | None = None) -> str:
        """
        Return a human-readable explanation of the daily care plan.

        For each pet, lists every task and states whether it was scheduled or
        skipped, with a reason for each skipped task. Appends a time summary.

        Args:
            plan: A pre-computed plan from generate_plan(). If None, generate_plan()
                  is called internally to avoid computing it twice.

        Returns:
            A formatted multi-line string describing the schedule.
        """
        if plan is None:
            plan = self.generate_plan()

        scheduled_ids: set[int] = {id(t) for t in plan}
        all_pairs = self._collect_all_tasks()

        if not all_pairs:
            return (
                f"No tasks found for any of {self.owner.name}'s pets. "
                "Add tasks to a pet before generating a plan."
            )

        lines: list[str] = [
            f"Daily Care Plan for {self.owner.name}",
            f"Available time: {self.owner.available_minutes_per_day} min",
            "=" * 50,
        ]

        # Group tasks by pet for readable output.
        pets_seen: dict[str, list[tuple[Pet, Task]]] = {}
        for pet, task in all_pairs:
            pets_seen.setdefault(pet.name, []).append((pet, task))

        mandatory_minutes = sum(t.duration_minutes for t in plan if t.mandatory)
        total_scheduled_minutes = sum(t.duration_minutes for t in plan)

        # Determine the time-exhaustion cutoff for skip-reason accuracy.
        # We replay the non-mandatory fill to know when time ran out.
        remaining_after_mandatory = (
            self.owner.available_minutes_per_day - mandatory_minutes
        )

        for pet_name, pairs in pets_seen.items():
            lines.append(f"\n  {pairs[0][0].name} ({pairs[0][0].species})")
            lines.append("  " + "-" * 30)

            for _pet, task in pairs:
                if id(task) in scheduled_ids:
                    tag = "[SCHEDULED]"
                    reason = f"{task.duration_minutes} min"
                    if task.mandatory:
                        reason += "  (mandatory)"
                    lines.append(f"    {tag}  {task.name} — {reason}")
                else:
                    tag = "[SKIPPED]  "
                    if task.completed:
                        reason = "already completed"
                    elif task.mandatory:
                        # Mandatory tasks are never skipped — this branch
                        # should not occur, but guard defensively.
                        reason = "mandatory but missing from plan (internal error)"
                    elif remaining_after_mandatory <= 0:
                        reason = "no time remaining after mandatory tasks"
                    else:
                        reason = (
                            f"insufficient time "
                            f"({task.duration_minutes} min needed, "
                            f"time already consumed by higher-priority tasks)"
                        )
                    lines.append(f"    {tag}  {task.name} — {reason}")

        lines.append("\n" + "=" * 50)
        lines.append(
            f"Total scheduled: {total_scheduled_minutes} min "
            f"/ {self.owner.available_minutes_per_day} min available"
        )

        if total_scheduled_minutes > self.owner.available_minutes_per_day:
            overrun = total_scheduled_minutes - self.owner.available_minutes_per_day
            lines.append(
                f"WARNING: mandatory tasks exceed available time by {overrun} min."
            )

        return "\n".join(lines)
