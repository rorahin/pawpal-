import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import date, timedelta

from pawpal_system import Task, Pet, Owner, Scheduler


def test_mark_complete_updates_status():
    task = Task(name="Feeding", category="feeding", duration_minutes=10, priority="high")
    assert task.completed == False
    task.mark_complete()
    assert task.completed == True


def test_add_task_increases_pet_task_count():
    pet = Pet(name="Buddy", species="dog", age=3, special_needs="None")
    assert len(pet.tasks) == 0
    task = Task(name="Walk", category="exercise", duration_minutes=20, priority="medium")
    pet.add_task(task)
    assert len(pet.tasks) == 1


class TestRecurringTasks:
    """Tests for Pet.complete_recurring_task() and the new-instance creation model."""

    def _make_daily_task(self, name: str = "Evening Walk") -> Task:
        """Return a daily recurring task due today."""
        return Task(
            name=name,
            category="exercise",
            duration_minutes=15,
            priority="high",
            recurrence="daily",
            due_date=date.today(),
        )

    def _make_pet_with_task(self, task: Task) -> Pet:
        """Return a Pet with the given task already added."""
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        pet.add_task(task)
        return pet

    def test_daily_recurring_creates_next_instance(self):
        """Completing a daily task appends exactly one new Task to pet.tasks."""
        task = self._make_daily_task()
        pet = self._make_pet_with_task(task)

        pet.complete_recurring_task(task)

        assert len(pet.tasks) == 2
        new_task = pet.tasks[1]
        assert new_task.due_date == date.today() + timedelta(days=1)
        assert new_task.completed == False

    def test_daily_recurring_marks_current_complete(self):
        """The original task instance must be marked completed=True after the call."""
        task = self._make_daily_task()
        pet = self._make_pet_with_task(task)

        pet.complete_recurring_task(task)

        assert task.completed == True

    def test_no_duplicate_on_second_completion(self):
        """Calling complete_recurring_task twice must not produce a third task."""
        task = self._make_daily_task()
        pet = self._make_pet_with_task(task)

        pet.complete_recurring_task(task)           # first call: creates new instance
        result = pet.complete_recurring_task(task)  # second call: duplicate protection

        assert result is None
        assert len(pet.tasks) == 2  # still 2, not 3

    def test_future_task_not_in_plan(self):
        """The newly created next-occurrence Task must not appear in today's plan."""
        task = self._make_daily_task()
        pet = self._make_pet_with_task(task)

        owner = Owner(name="Alex", available_minutes_per_day=120)
        owner.add_pet(pet)
        scheduler = Scheduler(owner)

        pet.complete_recurring_task(task)

        plan = scheduler.generate_plan()
        plan_names = [t.name for t in plan]
        assert "Evening Walk" not in plan_names

    def test_non_recurring_raises_on_complete_recurring_task(self):
        """Passing a non-recurring task to complete_recurring_task raises ValueError."""
        one_time_task = Task(
            name="Vet Visit",
            category="health",
            duration_minutes=60,
            priority="high",
            recurrence="none",
        )
        pet = self._make_pet_with_task(one_time_task)

        with pytest.raises(ValueError, match="non-recurring"):
            pet.complete_recurring_task(one_time_task)


class TestDetectTimeConflicts:
    """Tests for Scheduler.detect_time_conflicts()."""

    def _make_scheduler(self, pets: list["Pet"]) -> "Scheduler":
        """Build a minimal Owner containing the given pets and return a Scheduler for it."""
        owner = Owner(name="TestOwner", available_minutes_per_day=120)
        for pet in pets:
            owner.add_pet(pet)
        return Scheduler(owner)

    def test_detect_time_conflicts_same_time_returns_warning(self):
        """Two active tasks from different pets sharing the same scheduled_time produce a warning."""
        today = date.today()

        buddy = Pet(name="Buddy", species="dog", age=3, special_needs="")
        buddy.add_task(Task(
            name="Feeding",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time="08:00",
            due_date=today,
        ))

        luna = Pet(name="Luna", species="cat", age=5, special_needs="")
        luna.add_task(Task(
            name="Feeding",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time="08:00",
            due_date=today,
        ))

        scheduler = self._make_scheduler([buddy, luna])
        warnings = scheduler.detect_time_conflicts()

        assert len(warnings) == 1
        assert "08:00" in warnings[0]
        assert "cross-pet" in warnings[0]

    def test_detect_time_conflicts_no_overlap_returns_empty(self):
        """Tasks at different scheduled_times produce no warnings."""
        today = date.today()

        buddy = Pet(name="Buddy", species="dog", age=3, special_needs="")
        buddy.add_task(Task(
            name="Walk",
            category="exercise",
            duration_minutes=20,
            priority="high",
            scheduled_time="07:00",
            due_date=today,
        ))

        luna = Pet(name="Luna", species="cat", age=5, special_needs="")
        luna.add_task(Task(
            name="Feeding",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time="08:00",
            due_date=today,
        ))

        scheduler = self._make_scheduler([buddy, luna])
        warnings = scheduler.detect_time_conflicts()

        assert warnings == []
