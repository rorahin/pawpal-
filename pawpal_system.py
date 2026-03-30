"""
PawPal+ — Logic Layer
Core classes for managing pet care tasks and generating a daily schedule.

Ownership hierarchy:
    Owner  →  (many) Pet  →  (many) Task

The Scheduler takes an Owner and iterates Owner → Pets → Tasks to produce
a prioritized daily care plan within the owner's available time.
"""

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

# Maps priority labels to sort order (lower number = higher priority).
# Used by Scheduler.generate_plan() to rank non-mandatory tasks.
PRIORITY_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2}

_VALID_PRIORITIES: frozenset[str] = frozenset(PRIORITY_ORDER.keys())
_VALID_RECURRENCES: frozenset[str] = frozenset({"none", "daily", "weekly"})


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
      - recurrence must be one of: 'none', 'daily', 'weekly'

    mandatory tasks are always included in the schedule regardless of time.

    Recurrence:
      - 'none': one-shot task; marked permanently complete via self.completed.
      - 'daily': reappears every calendar day; tracked via last_completed_date.
      - 'weekly': reappears every 7 days; tracked via last_completed_date.
    """

    name: str
    category: str
    duration_minutes: int
    priority: str
    completed: bool = False
    mandatory: bool = False
    scheduled_time: str = ""
    """Time of day in 'HH:MM' 24-hour format. Empty string means unscheduled."""
    recurrence: str = "none"
    """Recurrence cadence. Allowed values: 'none', 'daily', 'weekly'."""
    due_date: date = field(default_factory=date.today)
    """Calendar date this task is due. Defaults to today if not provided."""
    last_completed_date: date | None = None
    """Date this recurring task was last completed. None until first completion."""

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
        if self.recurrence not in _VALID_RECURRENCES:
            raise ValueError(
                f"Invalid recurrence '{self.recurrence}'. "
                f"Must be one of: {sorted(_VALID_RECURRENCES)}."
            )

    def mark_complete(self) -> date | None:
        """
        Mark this task as completed.

        Non-recurring tasks ('none'):
            Sets self.completed = True. Raises RuntimeError if already complete.
            Returns None.

        Recurring tasks ('daily', 'weekly'):
            Sets self.completed = True on the CURRENT instance (marks this
            occurrence done).
            Sets self.last_completed_date = date.today() for record-keeping.
            Does NOT raise RuntimeError — same-day idempotency is enforced by
            duplicate protection in Pet.complete_recurring_task().
            Returns the next due_date:
              - 'daily'  → date.today() + timedelta(days=1)
              - 'weekly' → date.today() + timedelta(days=7)
        """
        if self.recurrence == "none":
            if self.completed:
                raise RuntimeError(
                    f"Task '{self.name}' is already marked as completed."
                )
            self.completed = True
            return None
        else:
            self.completed = True
            self.last_completed_date = date.today()
            if self.recurrence == "daily":
                return date.today() + timedelta(days=1)
            if self.recurrence == "weekly":
                return date.today() + timedelta(days=7)
            return None

    def is_due_today(self) -> bool:
        """
        Return True if this task should appear in today's care plan.

        Non-recurring: due if not yet completed.
        Daily: due if never completed, or last completed before today.
        Weekly: due if never completed, or last completed 7+ days ago.
        """
        today = date.today()
        if self.recurrence == "none":
            return not self.completed
        if self.recurrence == "daily":
            return self.last_completed_date is None or self.last_completed_date < today
        if self.recurrence == "weekly":
            return (
                self.last_completed_date is None
                or (today - self.last_completed_date).days >= 7
            )
        return False


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

    def complete_recurring_task(self, task: "Task") -> "Task | None":
        """
        Mark a recurring task complete and create the next occurrence.

        The completed flag is set on the current instance, and a brand-new Task
        object with the same attributes (but completed=False and an updated
        due_date) is appended to self.tasks and returned.

        Duplicate protection: if a future pending instance with the same name
        already exists (due_date > today, not completed), no new instance is
        created and None is returned.

        Args:
            task: A recurring Task that belongs to this pet.

        Returns:
            The newly created next-occurrence Task, or None if a future
            instance already exists.

        Raises:
            ValueError: if the task is non-recurring (recurrence == 'none').
        """
        if task.recurrence == "none":
            raise ValueError(
                f"Task '{task.name}' is non-recurring. "
                "Use task.mark_complete() directly for one-time tasks."
            )

        today = date.today()

        # Duplicate protection: scan for an already-pending future instance.
        task_name_lower = task.name.strip().lower()
        for existing in self.tasks:
            if (
                existing.name.strip().lower() == task_name_lower
                and existing.due_date > today
                and not existing.completed
            ):
                return None

        # Mark the current instance complete; receive the next due_date back.
        next_due = task.mark_complete()

        # Construct the next occurrence with identical attributes.
        next_task = Task(
            name=task.name,
            category=task.category,
            duration_minutes=task.duration_minutes,
            priority=task.priority,
            completed=False,
            mandatory=task.mandatory,
            scheduled_time=task.scheduled_time,
            recurrence=task.recurrence,
            due_date=next_due,
            last_completed_date=None,
        )

        self.tasks.append(next_task)
        return next_task


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

        today = date.today()
        for _pet, task in all_pairs:
            if task.completed or task.due_date > today:
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
                    today = date.today()
                    if task.completed or task.due_date > today:
                        if task.recurrence != "none" and task.due_date > today:
                            reason = "future occurrence — not due yet"
                        elif task.recurrence != "none":
                            reason = "already completed today"
                        else:
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

    def sort_by_time(
        self, tasks: list[tuple[Pet, Task]]
    ) -> list[tuple[Pet, Task]]:
        """
        Return a new list of (Pet, Task) pairs sorted chronologically by
        task.scheduled_time.

        Sorting rules:
          - Times must be in 'HH:MM' 24-hour format; string comparison is
            equivalent to numeric comparison for zero-padded HH:MM values.
          - Tasks with an empty or missing scheduled_time sort to the END.

        Args:
            tasks: A list of (Pet, Task) tuples, e.g. from _collect_all_tasks()
                   or a filtered subset.

        Returns:
            A new sorted list; the original is not mutated.
        """
        _SENTINEL = "\xff"  # Sorts after any valid HH:MM string.
        return sorted(
            tasks,
            key=lambda pair: pair[1].scheduled_time if pair[1].scheduled_time else _SENTINEL,
        )

    def filter_by_status(self, completed: bool) -> list[tuple[Pet, Task]]:
        """
        Return all (Pet, Task) pairs where task.completed matches the given value.

        Args:
            completed: True to retrieve completed tasks; False for incomplete.

        Returns:
            List of (Pet, Task) tuples matching the requested completion status.
        """
        return [
            (pet, task)
            for pet, task in self._collect_all_tasks()
            if task.completed == completed
        ]

    def filter_by_pet(self, pet_name: str) -> list[tuple[Pet, Task]]:
        """
        Return all (Pet, Task) pairs belonging to the named pet.

        The match is case-insensitive. If no pet with that name exists, an
        empty list is returned (not an error — callers decide how to handle it).

        Args:
            pet_name: The name of the pet to filter by.

        Returns:
            List of (Pet, Task) tuples for tasks owned by the named pet.
        """
        target = pet_name.strip().lower()
        return [
            (pet, task)
            for pet, task in self._collect_all_tasks()
            if pet.name.strip().lower() == target
        ]

    def detect_time_conflicts(self) -> list[str]:
        """
        Detect scheduling conflicts where two or more active tasks share the same
        scheduled_time on today's plan.

        Active tasks are those that:
          - are not completed
          - are due today (due_date <= date.today())
          - have a non-empty scheduled_time

        Returns:
            A list of human-readable warning strings. An empty list means no
            conflicts were found. Never raises; never mutates state.
        """
        today = date.today()

        # Step 1: Group active (pet_name, task_name) pairs by scheduled_time.
        time_slots: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
        for pet, task in self._collect_all_tasks():
            if task.completed or task.due_date > today or not task.scheduled_time:
                continue
            time_slots[task.scheduled_time].append((pet.name, task.name))

        # Step 2: Build a warning string for every slot that has 2+ entries.
        warnings: list[str] = []
        for time_slot, entries in sorted(time_slots.items()):
            if len(entries) < 2:
                continue

            pet_names = {name for name, _ in entries}
            conflict_type = "same pet" if len(pet_names) == 1 else "cross-pet"

            participants = ", ".join(
                f"{pet_name} — {task_name}" for pet_name, task_name in entries
            )
            warnings.append(
                f"Conflict at {time_slot}: {participants} ({conflict_type})"
            )

        return warnings

    def find_next_available_slot(self, duration: int) -> str:
        """
        Scan existing scheduled tasks sorted chronologically and find the first
        gap between consecutive tasks that fits `duration` minutes.

        Active tasks are those that are not completed and have a non-empty
        scheduled_time in HH:MM format.

        Rules:
          - The day starts at 08:00 and ends at 22:00.
          - Check the gap from 08:00 to the first task's start.
          - Check gaps between consecutive task-end and next task-start.
          - If no gap fits within the day, return the time right after the last
            scheduled task ends (may exceed 22:00 if tasks are packed).
          - If no active scheduled tasks exist, return "08:00".

        Args:
            duration: Desired slot length in minutes (must be > 0).

        Returns:
            A time string in HH:MM format.
        """
        if duration <= 0:
            raise ValueError(f"duration must be > 0, got {duration}.")

        today = date.today()

        # Collect (start_minutes, end_minutes) for active scheduled tasks.
        slots: list[tuple[int, int]] = []
        for pet, task in self._collect_all_tasks():
            if task.completed or task.due_date > today or not task.scheduled_time:
                continue
            try:
                hh, mm = task.scheduled_time.split(":")
                start = int(hh) * 60 + int(mm)
                end = start + task.duration_minutes
                slots.append((start, end))
            except (ValueError, AttributeError):
                continue

        if not slots:
            return "08:00"

        slots.sort(key=lambda s: s[0])

        day_start = 8 * 60   # 08:00 in minutes

        # Gap before the first task.
        first_start = slots[0][0]
        gap_start = max(day_start, 0)
        if first_start - gap_start >= duration:
            candidate = max(day_start, gap_start)
            return _minutes_to_hhmm(candidate)

        # Gaps between consecutive tasks.
        for i in range(len(slots) - 1):
            gap_start = slots[i][1]
            gap_end = slots[i + 1][0]
            if gap_end - gap_start >= duration:
                return _minutes_to_hhmm(gap_start)

        # No gap found — return time after the last task ends.
        return _minutes_to_hhmm(slots[-1][1])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _minutes_to_hhmm(minutes: int) -> str:
    """Convert an integer number of minutes since midnight to 'HH:MM' format."""
    hh = minutes // 60
    mm = minutes % 60
    return f"{hh:02d}:{mm:02d}"


# ---------------------------------------------------------------------------
# Data persistence — module-level functions
# ---------------------------------------------------------------------------

def save_data(owner: Owner, filename: str = "pawpal_data.json") -> None:
    """
    Serialize the full Owner → Pet → Task object graph to JSON and write it
    to `filename`.

    All date fields are stored as ISO-format strings ('YYYY-MM-DD').
    None values are preserved as JSON null.

    Args:
        owner:    The Owner whose data (including all pets and tasks) to save.
        filename: Destination file path. Defaults to 'pawpal_data.json'.
    """
    def _task_to_dict(task: Task) -> dict:
        return {
            "name": task.name,
            "category": task.category,
            "duration_minutes": task.duration_minutes,
            "priority": task.priority,
            "completed": task.completed,
            "mandatory": task.mandatory,
            "scheduled_time": task.scheduled_time,
            "recurrence": task.recurrence,
            "due_date": task.due_date.isoformat(),
            "last_completed_date": (
                task.last_completed_date.isoformat()
                if task.last_completed_date is not None
                else None
            ),
        }

    def _pet_to_dict(pet: Pet) -> dict:
        return {
            "name": pet.name,
            "species": pet.species,
            "age": pet.age,
            "special_needs": pet.special_needs,
            "tasks": [_task_to_dict(t) for t in pet.tasks],
        }

    payload = {
        "name": owner.name,
        "available_minutes_per_day": owner.available_minutes_per_day,
        "pets": [_pet_to_dict(p) for p in owner.pets],
    }

    with open(filename, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def load_data(filename: str = "pawpal_data.json") -> "Owner | None":
    """
    Load and reconstruct the full Owner → Pet → Task object graph from JSON.

    Args:
        filename: Source file path. Defaults to 'pawpal_data.json'.

    Returns:
        A fully reconstructed Owner object, or None if the file does not exist.

    Raises:
        json.JSONDecodeError: If the file exists but contains malformed JSON.
        KeyError / ValueError: If the file exists but has an unexpected schema.
    """
    if not os.path.exists(filename):
        return None

    with open(filename, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    def _dict_to_task(d: dict) -> Task:
        lcd_raw = d.get("last_completed_date")
        return Task(
            name=d["name"],
            category=d["category"],
            duration_minutes=d["duration_minutes"],
            priority=d["priority"],
            completed=d["completed"],
            mandatory=d["mandatory"],
            scheduled_time=d.get("scheduled_time", ""),
            recurrence=d.get("recurrence", "none"),
            due_date=date.fromisoformat(d["due_date"]),
            last_completed_date=(
                date.fromisoformat(lcd_raw) if lcd_raw is not None else None
            ),
        )

    def _dict_to_pet(d: dict) -> Pet:
        pet = Pet(
            name=d["name"],
            species=d["species"],
            age=d.get("age", 0),
            special_needs=d.get("special_needs", ""),
        )
        for task_dict in d.get("tasks", []):
            pet.tasks.append(_dict_to_task(task_dict))
        return pet

    owner = Owner(
        name=data["name"],
        available_minutes_per_day=data["available_minutes_per_day"],
    )
    for pet_dict in data.get("pets", []):
        owner.pets.append(_dict_to_pet(pet_dict))

    return owner
