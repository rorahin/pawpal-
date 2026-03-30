"""
PawPal+ — CLI Entry Point

Builds a sample owner/pet/task hierarchy, generates a daily care plan via the
Scheduler, and prints both a structured schedule view and the full explain_plan
output to stdout.
"""

from pawpal_system import Owner, Pet, Task, Scheduler


def main() -> None:
    """
    Construct sample data, run the scheduler, and print today's schedule
    followed by the full explain_plan explanation.
    """
    # --- Build owner ---
    owner = Owner(name="Alex", available_minutes_per_day=60)

    # --- Build Buddy (dog) ---
    buddy = Pet(name="Buddy", species="dog", age=3, special_needs="None")
    buddy.add_task(Task(name="Morning Walk",   category="exercise", duration_minutes=20, priority="high",   mandatory=True))
    buddy.add_task(Task(name="Feeding",        category="feeding",  duration_minutes=10, priority="high",   mandatory=False))
    buddy.add_task(Task(name="Teeth Brushing", category="grooming", duration_minutes=15, priority="low",    mandatory=False))

    # --- Build Luna (cat) ---
    luna = Pet(name="Luna", species="cat", age=5, special_needs="Indoor only")
    luna.add_task(Task(name="Feeding",     category="feeding",     duration_minutes=10, priority="high",   mandatory=False))
    luna.add_task(Task(name="Litter Box",  category="hygiene",     duration_minutes=5,  priority="medium", mandatory=False))
    luna.add_task(Task(name="Playtime",    category="enrichment",  duration_minutes=15, priority="medium", mandatory=False))

    owner.add_pet(buddy)
    owner.add_pet(luna)

    # --- Schedule (generate once, reuse for both print sections) ---
    scheduler = Scheduler(owner)
    plan = scheduler.generate_plan()

    # --- Section 1: structured schedule header ---
    border = "=" * 40
    print(border)
    print("Today's Schedule")
    print(border)
    for task in plan:
        mandatory_label = "yes" if task.mandatory else "no"
        print(f"  - {task.name} | {task.duration_minutes} min | priority: {task.priority} | mandatory: {mandatory_label}")

    # --- Section 2: full explain_plan output ---
    print()
    print("-" * 40)
    print()
    print(scheduler.explain_plan(plan))


if __name__ == "__main__":
    main()
