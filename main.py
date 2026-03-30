"""
PawPal+ — CLI Entry Point

Builds a sample owner/pet/task hierarchy, generates a daily care plan via the
Scheduler, and prints both a structured schedule view and the full explain_plan
output to stdout.

Phase 4 / Step 2 additions:
  - Tasks carry scheduled_time in 'HH:MM' format to drive chronological sorting.
  - Demonstrates sort_by_time(), filter_by_status(), and filter_by_pet().
"""

from datetime import date, timedelta

from pawpal_system import Owner, Pet, Task, Scheduler


def _format_task_row(pet_name: str, task: "Task") -> str:
    """Return a single human-readable line for one (pet, task) pair."""
    time_label = task.scheduled_time if task.scheduled_time else "unscheduled"
    return (
        f"  {pet_name:<8} | {task.name:<20} | {time_label:<11} | {task.duration_minutes} min"
    )


def main() -> None:
    """
    Construct sample data, run the scheduler, and print today's schedule
    followed by the full explain_plan explanation, then demonstrate sorting
    and filtering with clearly labeled output sections.
    """
    # --- Build owner ---
    owner = Owner(name="Alex", available_minutes_per_day=60)

    # --- Build Buddy (dog) ---
    # Times assigned intentionally out of chronological order to prove sorting.
    buddy = Pet(name="Buddy", species="dog", age=3, special_needs="None")
    buddy.add_task(Task(
        name="Morning Walk",
        category="exercise",
        duration_minutes=20,
        priority="high",
        mandatory=True,
        scheduled_time="07:00",
    ))
    buddy.add_task(Task(
        name="Feeding",
        category="feeding",
        duration_minutes=10,
        priority="high",
        mandatory=False,
        scheduled_time="14:00",
    ))
    buddy.add_task(Task(
        name="Teeth Brushing",
        category="grooming",
        duration_minutes=15,
        priority="low",
        mandatory=False,
        scheduled_time="",          # intentionally unscheduled — should sort last
    ))

    # --- Build Luna (cat) ---
    luna = Pet(name="Luna", species="cat", age=5, special_needs="Indoor only")
    luna.add_task(Task(
        name="Feeding",
        category="feeding",
        duration_minutes=10,
        priority="high",
        mandatory=False,
        scheduled_time="08:00",
    ))
    luna.add_task(Task(
        name="Litter Box",
        category="hygiene",
        duration_minutes=5,
        priority="medium",
        mandatory=False,
        scheduled_time="09:30",
    ))
    luna.add_task(Task(
        name="Playtime",
        category="enrichment",
        duration_minutes=15,
        priority="medium",
        mandatory=False,
        scheduled_time="16:45",
    ))

    owner.add_pet(buddy)
    owner.add_pet(luna)

    # --- Schedule (generate once, reuse for both print sections) ---
    scheduler = Scheduler(owner)
    plan = scheduler.generate_plan()

    # -----------------------------------------------------------------------
    # Section 1: structured schedule header
    # -----------------------------------------------------------------------
    border = "=" * 40
    print(border)
    print("Today's Schedule")
    print(border)
    for task in plan:
        mandatory_label = "yes" if task.mandatory else "no"
        time_label = task.scheduled_time if task.scheduled_time else "unscheduled"
        print(
            f"  - {task.name} | {task.duration_minutes} min"
            f" | priority: {task.priority}"
            f" | mandatory: {mandatory_label}"
            f" | time: {time_label}"
        )

    # -----------------------------------------------------------------------
    # Section 2: full explain_plan output
    # -----------------------------------------------------------------------
    print()
    print("-" * 40)
    print()
    print(scheduler.explain_plan(plan))

    # -----------------------------------------------------------------------
    # Section 3: Sorted tasks by time
    # -----------------------------------------------------------------------
    col_header = f"  {'Pet':<8} | {'Task':<20} | {'Time':<11} | Duration"
    divider    = "  " + "-" * (len(col_header) - 2)

    print()
    print("--- Sorted Tasks by Time ---")
    print(col_header)
    print(divider)
    all_tasks = scheduler._collect_all_tasks()
    for pet, task in scheduler.sort_by_time(all_tasks):
        print(_format_task_row(pet.name, task))

    # -----------------------------------------------------------------------
    # Section 4: Incomplete tasks
    # -----------------------------------------------------------------------
    print()
    print("--- Incomplete Tasks ---")
    print(col_header)
    print(divider)
    incomplete = scheduler.filter_by_status(completed=False)
    if incomplete:
        for pet, task in incomplete:
            print(_format_task_row(pet.name, task))
    else:
        print("  (none)")

    # -----------------------------------------------------------------------
    # Section 5: Tasks for Luna
    # -----------------------------------------------------------------------
    print()
    print("--- Tasks for Luna ---")
    print(col_header)
    print(divider)
    luna_tasks = scheduler.filter_by_pet("Luna")
    if luna_tasks:
        for pet, task in luna_tasks:
            print(_format_task_row(pet.name, task))
    else:
        print("  (none)")

    # -----------------------------------------------------------------------
    # Section 6: Conflict Detection Demo
    #
    # Two tasks are intentionally assigned the same scheduled_time ("08:00")
    # to demonstrate detect_time_conflicts().  Buddy's Feeding is re-created
    # here with scheduled_time="08:00" to collide with Luna's existing Feeding
    # (also "08:00").  We use a fresh owner/pet/scheduler so the demo is
    # self-contained and does not disturb the plan printed in sections 1–2.
    # -----------------------------------------------------------------------
    conflict_owner = Owner(name="Alex", available_minutes_per_day=120)

    buddy_c = Pet(name="Buddy", species="dog", age=3, special_needs="None")
    # Intentionally set to 08:00 to collide with Luna's Feeding below.
    buddy_c.add_task(Task(
        name="Feeding",
        category="feeding",
        duration_minutes=10,
        priority="high",
        scheduled_time="08:00",   # <-- deliberate collision time
    ))
    buddy_c.add_task(Task(
        name="Morning Walk",
        category="exercise",
        duration_minutes=20,
        priority="high",
        mandatory=True,
        scheduled_time="07:00",
    ))

    luna_c = Pet(name="Luna", species="cat", age=5, special_needs="Indoor only")
    # Intentionally set to 08:00 to collide with Buddy's Feeding above.
    luna_c.add_task(Task(
        name="Feeding",
        category="feeding",
        duration_minutes=10,
        priority="high",
        scheduled_time="08:00",   # <-- deliberate collision time
    ))
    luna_c.add_task(Task(
        name="Litter Box",
        category="hygiene",
        duration_minutes=5,
        priority="medium",
        scheduled_time="09:30",
    ))

    conflict_owner.add_pet(buddy_c)
    conflict_owner.add_pet(luna_c)

    conflict_scheduler = Scheduler(conflict_owner)
    conflict_warnings = conflict_scheduler.detect_time_conflicts()

    print()
    print("--- Conflict Warnings ---")
    if conflict_warnings:
        for warning in conflict_warnings:
            print(f"  {warning}")
    else:
        print("  No conflicts detected.")


def demo_recurring_tasks() -> None:
    """
    Demonstrate the recurring task redesign.

    When a recurring task is marked complete, a NEW Task instance is created
    for the next occurrence and appended to the pet's task list. The current
    instance is marked completed=True. The new instance is not visible in
    today's plan because its due_date is in the future.
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)
    border = "=" * 50

    # --- Setup ---
    owner = Owner(name="Alex", available_minutes_per_day=120)
    buddy = Pet(name="Buddy", species="dog", age=3, special_needs="None")
    owner.add_pet(buddy)

    evening_walk = Task(
        name="Evening Walk",
        category="exercise",
        duration_minutes=15,
        priority="high",
        mandatory=False,
        recurrence="daily",
        scheduled_time="18:00",
        due_date=today,
    )
    buddy.add_task(evening_walk)

    print()
    print(border)
    print("Recurring Task Demo")
    print(border)

    # --- Section 1: Initial state ---
    print()
    print("--- Section 1: Initial State ---")
    print(f"  Task name   : {evening_walk.name}")
    print(f"  Recurrence  : {evening_walk.recurrence}")
    print(f"  due_date    : {evening_walk.due_date}")
    print(f"  completed   : {evening_walk.completed}")
    print(f"  is_due_today: {evening_walk.is_due_today()}")   # expected: True

    # --- Section 2: Complete the recurring task ---
    scheduler = Scheduler(owner)
    next_task = buddy.complete_recurring_task(evening_walk)

    print()
    print("--- Section 2: After complete_recurring_task() ---")
    print("  CURRENT instance (original):")
    print(f"    completed            : {evening_walk.completed}")      # expected: True
    print(f"    due_date             : {evening_walk.due_date}")        # expected: today
    print(f"    last_completed_date  : {evening_walk.last_completed_date}")  # expected: today
    print()
    print("  NEW instance (next occurrence):")
    print(f"    completed            : {next_task.completed}")          # expected: False
    print(f"    due_date             : {next_task.due_date}")            # expected: tomorrow
    print(f"    last_completed_date  : {next_task.last_completed_date}") # expected: None

    # --- Section 3: Confirm new task absent from today's plan ---
    plan = scheduler.generate_plan()
    plan_names = [t.name for t in plan]

    print()
    print("--- Section 3: Today's Plan After Completion ---")
    print(f"  Tasks in plan : {plan_names if plan_names else '(none)'}")
    print(f"  'Evening Walk' in plan: {'Evening Walk' in plan_names}")  # expected: False

    # --- Section 4: Duplicate protection ---
    result = buddy.complete_recurring_task(evening_walk)

    print()
    print("--- Section 4: Duplicate Protection (call complete_recurring_task again) ---")
    print(f"  Return value        : {result}")                          # expected: None
    print(f"  Total tasks for Buddy: {len(buddy.tasks)}")               # expected: 2 (not 3)

    print()
    print(border)


if __name__ == "__main__":
    main()
    demo_recurring_tasks()
