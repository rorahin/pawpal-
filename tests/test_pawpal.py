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


# ===========================================================================
# TIER 1 — Foundation: Task and Pet/Owner validation
# ===========================================================================

class TestTaskValidation:
    """EC-11 through EC-15: Task construction guards and mark_complete idempotency."""

    def test_task_invalid_priority_raises_value_error(self):
        # EC-11: 'critical' is not in _VALID_PRIORITIES; only 'high', 'medium', 'low' are allowed.
        with pytest.raises(ValueError, match="priority"):
            Task(
                name="Medication",
                category="health",
                duration_minutes=10,
                priority="critical",
            )

    def test_task_zero_duration_raises_value_error(self):
        # EC-12: duration_minutes must be strictly > 0.
        with pytest.raises(ValueError, match="duration_minutes"):
            Task(
                name="Quick Check",
                category="health",
                duration_minutes=0,
                priority="high",
            )

    def test_task_negative_duration_raises_value_error(self):
        # EC-13: Negative duration is also not allowed.
        with pytest.raises(ValueError, match="duration_minutes"):
            Task(
                name="Quick Check",
                category="health",
                duration_minutes=-5,
                priority="high",
            )

    def test_task_invalid_recurrence_raises_value_error(self):
        # EC-14: 'hourly' is not in _VALID_RECURRENCES; only 'none', 'daily', 'weekly' are allowed.
        with pytest.raises(ValueError, match="recurrence"):
            Task(
                name="Insulin",
                category="health",
                duration_minutes=5,
                priority="high",
                recurrence="hourly",
            )

    def test_mark_complete_twice_on_non_recurring_raises_runtime_error(self):
        # EC-15: The second call must raise RuntimeError because completed is already True.
        task = Task(
            name="Vet Visit",
            category="health",
            duration_minutes=30,
            priority="high",
            recurrence="none",
        )
        task.mark_complete()  # first call — valid
        with pytest.raises(RuntimeError, match="already marked as completed"):
            task.mark_complete()  # second call — must raise


class TestDuplicateProtection:
    """EC-06 through EC-08: duplicate detection on add_task() and add_pet()."""

    def test_add_task_exact_duplicate_name_raises_value_error(self):
        # EC-06: Exact same name added twice to the same pet must be rejected.
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        pet.add_task(Task(name="Walk", category="exercise", duration_minutes=20, priority="high"))
        with pytest.raises(ValueError, match="already exists"):
            pet.add_task(Task(name="Walk", category="exercise", duration_minutes=20, priority="high"))

    def test_add_task_case_insensitive_duplicate_raises_value_error(self):
        # EC-07: Case-insensitive match — "WALK" collides with "walk" that already exists.
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        pet.add_task(Task(name="walk", category="exercise", duration_minutes=20, priority="high"))
        with pytest.raises(ValueError, match="already exists"):
            pet.add_task(Task(name="WALK", category="exercise", duration_minutes=20, priority="high"))

    def test_add_pet_case_insensitive_duplicate_raises_value_error(self):
        # EC-08: Case-insensitive match — "BUDDY" collides with "Buddy" already in owner.
        owner = Owner(name="Alex", available_minutes_per_day=60)
        owner.add_pet(Pet(name="Buddy", species="dog", age=3, special_needs=""))
        with pytest.raises(ValueError, match="already exists"):
            owner.add_pet(Pet(name="BUDDY", species="dog", age=3, special_needs=""))


# ===========================================================================
# TIER 2 — Core Scheduling
# ===========================================================================

class TestSchedulerCorePlan:
    """HP-01, HP-02, EC-01 through EC-05: plan generation correctness."""

    def _make_scheduler(self, owner: Owner) -> Scheduler:
        return Scheduler(owner)

    def test_mandatory_task_always_first_and_all_three_included(self):
        # HP-01: 60-min budget, 1 mandatory (20 min) + 2 non-mandatory (10+10 min).
        # All 3 must appear in the plan, and the mandatory task must be at index 0.
        owner = Owner(name="Alex", available_minutes_per_day=60)
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        mandatory_task = Task(
            name="Medication",
            category="health",
            duration_minutes=20,
            priority="high",
            mandatory=True,
        )
        opt_task_1 = Task(
            name="Walk",
            category="exercise",
            duration_minutes=10,
            priority="medium",
            mandatory=False,
        )
        opt_task_2 = Task(
            name="Grooming",
            category="grooming",
            duration_minutes=10,
            priority="low",
            mandatory=False,
        )
        pet.add_task(mandatory_task)
        pet.add_task(opt_task_1)
        pet.add_task(opt_task_2)
        owner.add_pet(pet)

        plan = self._make_scheduler(owner).generate_plan()

        assert len(plan) == 3
        # Mandatory task must be at position 0 (plan = list(mandatory) + non_mandatory).
        assert plan[0].mandatory is True
        assert plan[0].name == "Medication"

    def test_non_mandatory_tasks_ordered_high_medium_low(self):
        # HP-02: Three non-mandatory tasks with different priorities must appear
        # in high → medium → low order regardless of insertion order.
        owner = Owner(name="Alex", available_minutes_per_day=120)
        pet = Pet(name="Luna", species="cat", age=2, special_needs="")
        # Intentionally inserted out of priority order.
        pet.add_task(Task(name="Brush", category="grooming", duration_minutes=10, priority="low"))
        pet.add_task(Task(name="Play", category="enrichment", duration_minutes=10, priority="medium"))
        pet.add_task(Task(name="Feed", category="feeding", duration_minutes=10, priority="high"))
        owner.add_pet(pet)

        plan = self._make_scheduler(owner).generate_plan()

        priorities = [t.priority for t in plan]
        assert priorities == ["high", "medium", "low"]

    def test_mandatory_tasks_exceed_budget_still_all_in_plan_with_warning(self):
        # EC-04: Mandatory tasks collectively exceed available_minutes_per_day.
        # All mandatory tasks must still appear; explain_plan() must contain "WARNING".
        owner = Owner(name="Alex", available_minutes_per_day=30)
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        pet.add_task(Task(
            name="Medication A",
            category="health",
            duration_minutes=20,
            priority="high",
            mandatory=True,
        ))
        pet.add_task(Task(
            name="Medication B",
            category="health",
            duration_minutes=20,
            priority="high",
            mandatory=True,
        ))
        owner.add_pet(pet)
        scheduler = self._make_scheduler(owner)
        plan = scheduler.generate_plan()

        mandatory_in_plan = [t for t in plan if t.mandatory]
        assert len(mandatory_in_plan) == 2

        explanation = scheduler.explain_plan(plan)
        assert "WARNING" in explanation

    def test_single_mandatory_task_exceeds_full_budget_in_plan_with_warning(self):
        # EC-05: One mandatory task alone exceeds the entire time budget.
        # It must still appear in the plan, and explain_plan() must warn.
        owner = Owner(name="Alex", available_minutes_per_day=10)
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        pet.add_task(Task(
            name="Surgery Prep",
            category="health",
            duration_minutes=60,
            priority="high",
            mandatory=True,
        ))
        owner.add_pet(pet)
        scheduler = self._make_scheduler(owner)
        plan = scheduler.generate_plan()

        assert len(plan) == 1
        assert plan[0].name == "Surgery Prep"

        explanation = scheduler.explain_plan(plan)
        assert "WARNING" in explanation

    def test_owner_with_no_pets_returns_empty_plan(self):
        # EC-01: Owner with zero pets. generate_plan() must return [].
        # explain_plan() must return the "No tasks found" sentinel message.
        owner = Owner(name="Alex", available_minutes_per_day=60)
        scheduler = self._make_scheduler(owner)

        plan = scheduler.generate_plan()
        assert plan == []

        explanation = scheduler.explain_plan(plan)
        assert "No tasks found" in explanation

    def test_pet_with_no_tasks_returns_empty_plan_without_crash(self):
        # EC-02: Owner has a pet, but the pet has zero tasks.
        # generate_plan() must return [] without raising.
        owner = Owner(name="Alex", available_minutes_per_day=60)
        owner.add_pet(Pet(name="Ghost", species="cat", age=1, special_needs=""))
        scheduler = self._make_scheduler(owner)

        plan = scheduler.generate_plan()
        assert plan == []

    def test_all_tasks_completed_returns_empty_plan(self):
        # EC-03: Every task is already completed — generate_plan() must return [].
        owner = Owner(name="Alex", available_minutes_per_day=60)
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        task = Task(name="Walk", category="exercise", duration_minutes=20, priority="high")
        task.mark_complete()
        pet.add_task(task)
        owner.add_pet(pet)

        plan = self._make_scheduler(owner).generate_plan()
        assert plan == []


# ===========================================================================
# TIER 3 — Recurring Logic
# ===========================================================================

class TestRecurringLogicExtended:
    """EC-16, EC-26, EC-27: is_due_today() weekly cadence and ValueError guard."""

    def test_weekly_task_not_due_3_days_after_completion(self):
        # EC-26: Weekly task completed 3 days ago must NOT be due today.
        task = Task(
            name="Bath",
            category="grooming",
            duration_minutes=30,
            priority="medium",
            recurrence="weekly",
        )
        task.last_completed_date = date.today() - timedelta(days=3)
        assert task.is_due_today() is False

    def test_weekly_task_is_due_exactly_7_days_after_completion(self):
        # EC-27: Weekly task completed exactly 7 days ago must BE due today.
        # is_due_today() uses >= 7, so day 7 is the first eligible day.
        task = Task(
            name="Bath",
            category="grooming",
            duration_minutes=30,
            priority="medium",
            recurrence="weekly",
        )
        task.last_completed_date = date.today() - timedelta(days=7)
        assert task.is_due_today() is True

    def test_complete_recurring_task_on_non_recurring_raises_value_error(self):
        # EC-16: complete_recurring_task() must raise ValueError for recurrence="none".
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        task = Task(
            name="One-time Bath",
            category="grooming",
            duration_minutes=20,
            priority="low",
            recurrence="none",
        )
        pet.add_task(task)
        with pytest.raises(ValueError):
            pet.complete_recurring_task(task)


# ===========================================================================
# TIER 4 — Conflict Detection
# ===========================================================================

class TestConflictDetectionExtended:
    """EC-18 through EC-20: same-pet conflict, completed/future task exclusion."""

    def _make_scheduler(self, pets: list[Pet]) -> Scheduler:
        owner = Owner(name="TestOwner", available_minutes_per_day=120)
        for pet in pets:
            owner.add_pet(pet)
        return Scheduler(owner)

    def test_two_tasks_from_same_pet_same_time_produces_one_warning_with_same_pet_label(self):
        # EC-18: Both conflicting tasks belong to the SAME pet — conflict_type must be "same pet".
        today = date.today()
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        pet.add_task(Task(
            name="Feeding",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time="08:00",
            due_date=today,
        ))
        pet.add_task(Task(
            name="Medication",
            category="health",
            duration_minutes=5,
            priority="high",
            scheduled_time="08:00",
            due_date=today,
        ))

        scheduler = self._make_scheduler([pet])
        warnings = scheduler.detect_time_conflicts()

        assert len(warnings) == 1
        assert "same pet" in warnings[0]

    def test_completed_task_at_conflicting_time_excluded_no_false_warning(self):
        # EC-19: A completed task sharing a time slot with an active task must not trigger a warning.
        # detect_time_conflicts() skips completed tasks, so only 1 active task remains — no conflict.
        today = date.today()
        pet = Pet(name="Luna", species="cat", age=4, special_needs="")
        active_task = Task(
            name="Feeding",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time="09:00",
            due_date=today,
        )
        completed_task = Task(
            name="Play",
            category="enrichment",
            duration_minutes=15,
            priority="medium",
            scheduled_time="09:00",
            due_date=today,
            completed=True,
        )
        pet.add_task(active_task)
        pet.add_task(completed_task)

        scheduler = self._make_scheduler([pet])
        warnings = scheduler.detect_time_conflicts()

        assert warnings == []

    def test_future_due_task_at_conflicting_time_excluded_no_false_warning(self):
        # EC-20: A task whose due_date is in the future must be excluded from conflict detection.
        # Only the active (today-due) task remains at that slot — no conflict should be raised.
        today = date.today()
        tomorrow = today + timedelta(days=1)
        pet = Pet(name="Luna", species="cat", age=4, special_needs="")
        active_task = Task(
            name="Feeding",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time="09:00",
            due_date=today,
        )
        future_task = Task(
            name="Play",
            category="enrichment",
            duration_minutes=15,
            priority="medium",
            scheduled_time="09:00",
            due_date=tomorrow,
        )
        pet.add_task(active_task)
        pet.add_task(future_task)

        scheduler = self._make_scheduler([pet])
        warnings = scheduler.detect_time_conflicts()

        assert warnings == []


# ===========================================================================
# TIER 5 — Filter and Sort
# ===========================================================================

class TestFilterAndSort:
    """HP-07 through HP-09, EC-21 through EC-24: filter_by_status, filter_by_pet, sort_by_time."""

    def _make_scheduler_with_two_pets(self) -> tuple[Scheduler, Pet, Pet]:
        """
        Build a scheduler with two pets (Luna and Buddy) each holding two tasks.
        Luna has one completed and one incomplete task.
        Buddy has one incomplete task.
        Returns (scheduler, luna, buddy).
        """
        owner = Owner(name="Alex", available_minutes_per_day=120)

        luna = Pet(name="Luna", species="cat", age=5, special_needs="")
        luna_completed = Task(
            name="Vet Visit",
            category="health",
            duration_minutes=60,
            priority="high",
            completed=True,
        )
        luna_incomplete = Task(
            name="Feeding",
            category="feeding",
            duration_minutes=10,
            priority="high",
        )
        luna.add_task(luna_completed)
        luna.add_task(luna_incomplete)

        buddy = Pet(name="Buddy", species="dog", age=3, special_needs="")
        buddy_task = Task(
            name="Walk",
            category="exercise",
            duration_minutes=20,
            priority="medium",
        )
        buddy.add_task(buddy_task)

        owner.add_pet(luna)
        owner.add_pet(buddy)
        return Scheduler(owner), luna, buddy

    def test_filter_by_status_incomplete_returns_only_incomplete_tasks(self):
        # HP-07: 1 completed + 1 incomplete across pets. filter_by_status(False) must
        # return only the incomplete tasks (2 total: Luna's Feeding and Buddy's Walk).
        scheduler, _, _ = self._make_scheduler_with_two_pets()

        result = scheduler.filter_by_status(completed=False)

        assert all(task.completed is False for _, task in result)
        # Both incomplete tasks must be present.
        task_names = {task.name for _, task in result}
        assert "Feeding" in task_names
        assert "Walk" in task_names
        assert "Vet Visit" not in task_names

    def test_filter_by_pet_returns_only_named_pets_tasks(self):
        # HP-08: filter_by_pet("Luna") must return Luna's tasks only — no Buddy tasks.
        scheduler, _, _ = self._make_scheduler_with_two_pets()

        result = scheduler.filter_by_pet("Luna")

        assert len(result) == 2
        assert all(pet.name == "Luna" for pet, _ in result)
        task_names = {task.name for _, task in result}
        assert "Walk" not in task_names  # Buddy's task must be absent

    def test_filter_by_pet_nonexistent_name_returns_empty_list(self):
        # EC-21: Non-existent pet name must return [] without raising.
        scheduler, _, _ = self._make_scheduler_with_two_pets()

        result = scheduler.filter_by_pet("Phantom")

        assert result == []

    def test_filter_by_status_all_completed_returns_empty_list(self):
        # EC-22: When every task is completed, filter_by_status(completed=False)
        # must return [] without raising.
        owner = Owner(name="Alex", available_minutes_per_day=60)
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")
        task = Task(name="Walk", category="exercise", duration_minutes=20, priority="high")
        task.mark_complete()
        pet.add_task(task)
        owner.add_pet(pet)
        scheduler = Scheduler(owner)

        result = scheduler.filter_by_status(completed=False)

        assert result == []

    def test_sort_by_time_scheduled_first_unscheduled_last(self):
        # HP-09: Mix of scheduled and unscheduled tasks. sort_by_time() must place
        # all tasks with scheduled_time first (ascending), then unscheduled tasks last.
        owner = Owner(name="Alex", available_minutes_per_day=120)
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")

        # Inserted out of chronological order intentionally.
        pet.add_task(Task(
            name="Evening Walk",
            category="exercise",
            duration_minutes=20,
            priority="medium",
            scheduled_time="18:00",
        ))
        pet.add_task(Task(
            name="Unscheduled Task",
            category="other",
            duration_minutes=5,
            priority="low",
            scheduled_time="",
        ))
        pet.add_task(Task(
            name="Morning Feed",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time="07:00",
        ))

        owner.add_pet(pet)
        scheduler = Scheduler(owner)

        all_pairs = scheduler._collect_all_tasks()
        sorted_pairs = scheduler.sort_by_time(all_pairs)
        times = [task.scheduled_time for _, task in sorted_pairs]

        # First two should be "07:00" then "18:00", last should be unscheduled ("").
        assert times[0] == "07:00"
        assert times[1] == "18:00"
        assert times[2] == ""

    def test_sort_by_time_empty_list_returns_empty(self):
        # EC-23: Passing an empty list to sort_by_time() must return [] without crash.
        owner = Owner(name="Alex", available_minutes_per_day=60)
        scheduler = Scheduler(owner)

        result = scheduler.sort_by_time([])

        assert result == []

    def test_sort_by_time_already_sorted_input_returns_same_order(self):
        # EC-24: Already-sorted input must produce the same correct order (idempotency).
        owner = Owner(name="Alex", available_minutes_per_day=120)
        pet = Pet(name="Luna", species="cat", age=3, special_needs="")
        pet.add_task(Task(
            name="Early Feed",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time="07:00",
        ))
        pet.add_task(Task(
            name="Late Play",
            category="enrichment",
            duration_minutes=15,
            priority="medium",
            scheduled_time="20:00",
        ))
        owner.add_pet(pet)
        scheduler = Scheduler(owner)

        all_pairs = scheduler._collect_all_tasks()
        # Input is already in ascending time order ("07:00", "20:00").
        sorted_once = scheduler.sort_by_time(all_pairs)
        sorted_twice = scheduler.sort_by_time(sorted_once)

        times_once = [task.scheduled_time for _, task in sorted_once]
        times_twice = [task.scheduled_time for _, task in sorted_twice]
        assert times_once == ["07:00", "20:00"]
        assert times_twice == times_once


# ===========================================================================
# PHASE 5 STEP 2 — Required algorithmic behavior tests
# ===========================================================================

class TestPhase5RequiredBehaviors:
    """
    Three focused tests required for Phase 5 Step 2.

    A. Sorting correctness  — tasks inserted out of chronological order;
                              assert on task *names* in the correct sequence.
    B. Recurrence logic     — complete a daily task and verify: task count,
                              next due date, and original completion state.
    C. Conflict detection   — two tasks at the same time; assert at least one
                              warning is produced and that the shared time and
                              at least one task name appear in the warning text.
    """

    # -----------------------------------------------------------------------
    # A. SORTING CORRECTNESS
    # -----------------------------------------------------------------------

    def test_sort_by_time_out_of_order_tasks_returns_correct_name_sequence(self):
        """
        Tasks inserted in reverse chronological order must emerge sorted
        earliest-to-latest, and unscheduled tasks must be last.

        Insertion order : Evening Walk (18:00) → Lunch Meds (12:00) →
                          Morning Feed (07:00) → Unscheduled Groom ("")
        Expected order  : Morning Feed → Lunch Meds → Evening Walk →
                          Unscheduled Groom
        """
        owner = Owner(name="Alex", available_minutes_per_day=120)
        pet = Pet(name="Buddy", species="dog", age=3, special_needs="")

        # Inserted intentionally out of chronological order.
        pet.add_task(Task(
            name="Evening Walk",
            category="exercise",
            duration_minutes=20,
            priority="medium",
            scheduled_time="18:00",
        ))
        pet.add_task(Task(
            name="Lunch Meds",
            category="health",
            duration_minutes=5,
            priority="high",
            scheduled_time="12:00",
        ))
        pet.add_task(Task(
            name="Morning Feed",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time="07:00",
        ))
        pet.add_task(Task(
            name="Unscheduled Groom",
            category="grooming",
            duration_minutes=15,
            priority="low",
            scheduled_time="",  # no time — must sort to end
        ))

        owner.add_pet(pet)
        scheduler = Scheduler(owner)

        all_pairs = scheduler._collect_all_tasks()
        sorted_pairs = scheduler.sort_by_time(all_pairs)
        sorted_names = [task.name for _, task in sorted_pairs]

        assert sorted_names == [
            "Morning Feed",
            "Lunch Meds",
            "Evening Walk",
            "Unscheduled Groom",
        ]

    # -----------------------------------------------------------------------
    # B. RECURRENCE LOGIC
    # -----------------------------------------------------------------------

    def test_complete_daily_task_creates_one_next_occurrence_with_correct_due_date(self):
        """
        After calling complete_recurring_task() on a daily task:
          - pet.tasks must contain exactly 2 tasks (original + new occurrence).
          - The new task must have due_date == today + 1 day.
          - The new task must be incomplete (completed=False).
          - The original task must be marked completed=True.
        """
        today = date.today()
        tomorrow = today + timedelta(days=1)

        pet = Pet(name="Luna", species="cat", age=4, special_needs="")
        daily_task = Task(
            name="Daily Feeding",
            category="feeding",
            duration_minutes=10,
            priority="high",
            recurrence="daily",
            due_date=today,
        )
        pet.add_task(daily_task)

        next_task = pet.complete_recurring_task(daily_task)

        # Exactly one new occurrence was appended.
        assert len(pet.tasks) == 2

        # New occurrence has the correct next due date.
        assert next_task is not None
        assert next_task.due_date == tomorrow

        # New occurrence is not yet completed.
        assert next_task.completed is False

        # Original instance is now marked complete.
        assert daily_task.completed is True

    # -----------------------------------------------------------------------
    # C. CONFLICT DETECTION
    # -----------------------------------------------------------------------

    def test_two_tasks_at_same_time_produces_warning_containing_time_and_task_names(self):
        """
        Two active tasks assigned the same scheduled_time must produce at least
        one warning string that contains:
          - the shared time slot
          - both task names
        This guards against a silent no-op when a real scheduling collision occurs.
        """
        today = date.today()
        shared_time = "09:00"

        buddy = Pet(name="Buddy", species="dog", age=3, special_needs="")
        buddy.add_task(Task(
            name="Morning Walk",
            category="exercise",
            duration_minutes=20,
            priority="high",
            scheduled_time=shared_time,
            due_date=today,
        ))

        luna = Pet(name="Luna", species="cat", age=5, special_needs="")
        luna.add_task(Task(
            name="Morning Feeding",
            category="feeding",
            duration_minutes=10,
            priority="high",
            scheduled_time=shared_time,
            due_date=today,
        ))

        owner = Owner(name="Alex", available_minutes_per_day=120)
        owner.add_pet(buddy)
        owner.add_pet(luna)
        scheduler = Scheduler(owner)

        warnings = scheduler.detect_time_conflicts()

        # At least one warning must be raised.
        assert len(warnings) >= 1

        # The warning must reference the shared time slot.
        combined = " ".join(warnings)
        assert shared_time in combined

        # Both task names must appear somewhere in the warnings.
        assert "Morning Walk" in combined
        assert "Morning Feeding" in combined
