import streamlit as st
from pawpal_system import Task, Pet, Owner, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# ---------------------------------------------------------------------------
# Session state bootstrap
# ---------------------------------------------------------------------------
# The Owner (and all pets/tasks nested inside it) lives in session_state so it
# survives Streamlit reruns.  We never recreate it on reruns — only on first load.
if "owner" not in st.session_state:
    st.session_state["owner"] = Owner(name="", available_minutes_per_day=60)

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("PawPal+")
st.markdown(
    "Plan your pet's daily care tasks, generate a time-bounded schedule, "
    "and see exactly what gets scheduled and why."
)
st.divider()

# ---------------------------------------------------------------------------
# Section 1: Owner
# ---------------------------------------------------------------------------
st.subheader("Owner")

owner_name = st.text_input("Owner name", value=st.session_state["owner"].name)
available_minutes = st.number_input(
    "Available minutes per day",
    min_value=1,
    max_value=1440,
    value=st.session_state["owner"].available_minutes_per_day,
)

# Sync changes back to the Owner object immediately (no button needed — these
# are scalar fields, not additions to a collection).
st.session_state["owner"].name = owner_name
st.session_state["owner"].available_minutes_per_day = int(available_minutes)

st.divider()

# ---------------------------------------------------------------------------
# Section 2: Add Pet
# ---------------------------------------------------------------------------
st.subheader("Add Pet")

col_pet1, col_pet2 = st.columns(2)
with col_pet1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col_pet2:
    species = st.selectbox("Species", ["dog", "cat", "other"])

if st.button("Add pet"):
    new_pet = Pet(name=pet_name, species=species, age=0, special_needs="")
    try:
        st.session_state["owner"].add_pet(new_pet)
        st.success(f"{pet_name} added successfully!")
    except ValueError as e:
        st.error(str(e))

# Show the current pet roster so the user can see what exists.
owner: Owner = st.session_state["owner"]
if owner.pets:
    st.caption(
        "Pets registered: "
        + ", ".join(f"{p.name} ({p.species})" for p in owner.pets)
    )
else:
    st.info("No pets yet. Add one above.")

st.divider()

# ---------------------------------------------------------------------------
# Section 3: Add Task
# ---------------------------------------------------------------------------
st.subheader("Add Task")

col1, col2, col3 = st.columns(3)
with col1:
    task_title = st.text_input("Task title", value="Morning walk")
with col2:
    duration = st.number_input(
        "Duration (minutes)", min_value=1, max_value=240, value=20
    )
with col3:
    priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

col4, col5, col6 = st.columns(3)
with col4:
    # Pet selector — only shown if there are pets registered.
    if owner.pets:
        pet_options = [p.name for p in owner.pets]
        selected_pet_name = st.selectbox("Assign to pet", pet_options)
    else:
        selected_pet_name = None
        st.caption("Add a pet first.")
with col5:
    scheduled_time_input = st.text_input(
        "Scheduled time (HH:MM, optional)",
        value="",
        placeholder="e.g. 08:00",
        help="Leave blank to leave the task unscheduled. Use 24-hour format.",
    )
with col6:
    is_mandatory = st.checkbox("Mandatory task", value=False)

if st.button("Add task"):
    if not owner.pets:
        st.warning("Add a pet first before adding tasks.")
    else:
        # Find the target pet by name.
        target_pet: Pet | None = next(
            (p for p in owner.pets if p.name == selected_pet_name), None
        )
        if target_pet is None:
            st.error("Selected pet not found. Please refresh and try again.")
        else:
            # Validate scheduled_time format before constructing the Task.
            raw_time = scheduled_time_input.strip()
            time_valid = True
            if raw_time:
                import re
                if not re.match(r"^\d{2}:\d{2}$", raw_time):
                    st.error(
                        "Scheduled time must be in HH:MM format (e.g. 08:00). "
                        "Leave blank to leave the task unscheduled."
                    )
                    time_valid = False

            if time_valid:
                try:
                    new_task = Task(
                        name=task_title,
                        category="general",
                        duration_minutes=int(duration),
                        priority=priority,
                        mandatory=is_mandatory,
                        scheduled_time=raw_time,
                    )
                    target_pet.add_task(new_task)
                    st.success(
                        f"Task '{task_title}' added to {target_pet.name}!"
                    )
                except ValueError as e:
                    st.error(str(e))

st.divider()

# ---------------------------------------------------------------------------
# Section 4: Current Tasks (all pets, sorted and filtered, with live conflicts)
# ---------------------------------------------------------------------------
st.subheader("Current Tasks")

if not owner.pets:
    st.info("No pets yet. Add a pet and some tasks to see them here.")
else:
    has_any_tasks = any(len(p.tasks) > 0 for p in owner.pets)
    if not has_any_tasks:
        st.info("No tasks yet. Add a task above to get started.")
    else:
        # Build a Scheduler so we can use its query and conflict methods.
        scheduler = Scheduler(owner)

        # ------------------------------------------------------------------
        # Live conflict warnings — surfaced here so the owner sees them
        # immediately, without needing to press "Generate schedule".
        # ------------------------------------------------------------------
        raw_conflicts = scheduler.detect_time_conflicts()
        if raw_conflicts:
            st.markdown("**Scheduling Conflicts Detected**")
            for raw in raw_conflicts:
                # Parse the raw conflict string produced by detect_time_conflicts()
                # and rewrite it in plain, pet-owner-friendly language.
                #
                # Raw format:
                #   "Conflict at 08:00: Buddy — Feeding, Luna — Feeding (cross-pet)"
                #   "Conflict at 07:00: Buddy — Walk, Buddy — Run (same pet)"
                try:
                    after_conflict = raw.split("Conflict at ", 1)[1]
                    time_part, rest = after_conflict.split(": ", 1)

                    if " (cross-pet)" in rest:
                        participants_str = rest.replace(" (cross-pet)", "").strip()
                        conflict_kind = "across different pets"
                    elif " (same pet)" in rest:
                        participants_str = rest.replace(" (same pet)", "").strip()
                        conflict_kind = "for the same pet"
                    else:
                        participants_str = rest.strip()
                        conflict_kind = ""

                    entries = [e.strip() for e in participants_str.split(",")]
                    entry_phrases = [
                        f"{e.split(' — ')[1]} ({e.split(' — ')[0]})"
                        if " — " in e else e
                        for e in entries
                    ]
                    tasks_listed = " and ".join(entry_phrases)

                    friendly = (
                        f"Time conflict at {time_part}: {tasks_listed} are both "
                        f"scheduled at the same time {conflict_kind}. "
                        f"Adjust one task's scheduled time to resolve this."
                    )
                except Exception:
                    # Parsing failure falls back to the raw string rather than
                    # crashing the UI.
                    friendly = raw

                st.warning(friendly)

        # ------------------------------------------------------------------
        # Filter controls — status filter uses Scheduler.filter_by_status();
        # pet filter uses Scheduler.filter_by_pet().
        # ------------------------------------------------------------------
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            status_filter = st.selectbox(
                "Show tasks",
                ["All tasks", "Incomplete only", "Completed only"],
                index=0,
            )
        with col_f2:
            pet_filter_options = ["All pets"] + [p.name for p in owner.pets]
            pet_filter = st.selectbox("Filter by pet", pet_filter_options, index=0)

        # Resolve the task set using Scheduler methods — no inline logic.
        if status_filter == "Incomplete only":
            task_pairs = scheduler.filter_by_status(completed=False)
        elif status_filter == "Completed only":
            task_pairs = scheduler.filter_by_status(completed=True)
        else:
            task_pairs = scheduler._collect_all_tasks()

        if pet_filter != "All pets":
            # Delegate to Scheduler.filter_by_pet() — case-insensitive, no
            # inline list comprehension needed.
            pet_only = scheduler.filter_by_pet(pet_filter)
            # Intersect with the status-filtered set by task identity.
            status_ids = {id(task) for _pet, task in task_pairs}
            task_pairs = [(pet, task) for pet, task in pet_only if id(task) in status_ids]

        # Sort chronologically using Scheduler.sort_by_time() — always applied.
        task_pairs = scheduler.sort_by_time(task_pairs)

        if not task_pairs:
            st.info("No tasks match the current filter.")
        else:
            task_rows = [
                {
                    "Pet": pet.name,
                    "Task": task.name,
                    "Time": task.scheduled_time if task.scheduled_time else "unscheduled",
                    "Duration (min)": task.duration_minutes,
                    "Priority": task.priority,
                    "Mandatory": task.mandatory,
                    "Completed": task.completed,
                }
                for pet, task in task_pairs
            ]
            st.dataframe(task_rows, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Section 5: Manage Tasks (mark complete / remove)
# ---------------------------------------------------------------------------
st.subheader("Manage Tasks")

if not owner.pets:
    st.info("No pets yet. Add a pet and tasks to manage them here.")
else:
    has_any_tasks = any(len(p.tasks) > 0 for p in owner.pets)
    if not has_any_tasks:
        st.info("No tasks yet. Add tasks above to manage them here.")
    else:
        # Pet selector for management actions.
        manage_pet_options = [p.name for p in owner.pets]
        manage_pet_name = st.selectbox(
            "Select pet", manage_pet_options, key="manage_pet_select"
        )
        manage_pet: Pet | None = next(
            (p for p in owner.pets if p.name == manage_pet_name), None
        )

        if manage_pet and manage_pet.tasks:
            task_options = [t.name for t in manage_pet.tasks]
            manage_task_name = st.selectbox(
                "Select task", task_options, key="manage_task_select"
            )
            manage_task: Task | None = next(
                (t for t in manage_pet.tasks if t.name == manage_task_name), None
            )

            col_m1, col_m2 = st.columns(2)

            with col_m1:
                if st.button("Mark complete", key="btn_complete"):
                    if manage_task is None:
                        st.error("Task not found. Please refresh and try again.")
                    elif manage_task.completed:
                        st.warning(
                            f"'{manage_task.name}' is already marked as complete."
                        )
                    else:
                        try:
                            manage_task.mark_complete()
                            st.success(
                                f"'{manage_task.name}' marked complete for {manage_pet.name}!"
                            )
                        except RuntimeError as e:
                            st.error(str(e))

            with col_m2:
                if st.button("Remove task", key="btn_remove"):
                    if manage_task is None:
                        st.error("Task not found. Please refresh and try again.")
                    else:
                        try:
                            manage_pet.remove_task(manage_task_name)
                            st.success(
                                f"Task '{manage_task_name}' removed from {manage_pet.name}."
                            )
                        except ValueError as e:
                            st.error(str(e))
        elif manage_pet:
            st.info(f"{manage_pet.name} has no tasks yet.")

st.divider()

# ---------------------------------------------------------------------------
# Section 6: Generate Schedule
# ---------------------------------------------------------------------------
st.subheader("Generate Schedule")

if st.button("Generate schedule"):
    has_tasks = owner.pets and any(len(p.tasks) > 0 for p in owner.pets)
    if not owner.pets:
        st.warning("Add a pet first before generating a schedule.")
    elif not has_tasks:
        st.warning("Add at least one task before generating a schedule.")
    else:
        try:
            scheduler = Scheduler(owner)
            plan = scheduler.generate_plan()

            # ------------------------------------------------------------------
            # Conflict warnings — displayed before the schedule so the owner
            # sees them first and knows which tasks need adjustment.
            # ------------------------------------------------------------------
            raw_conflicts = scheduler.detect_time_conflicts()
            if raw_conflicts:
                st.markdown("**Scheduling Conflicts Detected**")
                for raw in raw_conflicts:
                    try:
                        after_conflict = raw.split("Conflict at ", 1)[1]
                        time_part, rest = after_conflict.split(": ", 1)

                        if " (cross-pet)" in rest:
                            participants_str = rest.replace(" (cross-pet)", "").strip()
                            conflict_kind = "across different pets"
                        elif " (same pet)" in rest:
                            participants_str = rest.replace(" (same pet)", "").strip()
                            conflict_kind = "for the same pet"
                        else:
                            participants_str = rest.strip()
                            conflict_kind = ""

                        entries = [e.strip() for e in participants_str.split(",")]
                        entry_phrases = [
                            f"{e.split(' — ')[1]} ({e.split(' — ')[0]})"
                            if " — " in e else e
                            for e in entries
                        ]
                        tasks_listed = " and ".join(entry_phrases)

                        friendly = (
                            f"Time conflict at {time_part}: {tasks_listed} are both "
                            f"scheduled at the same time {conflict_kind}. "
                            f"Adjust one task's scheduled time to resolve this."
                        )
                    except Exception:
                        friendly = raw

                    st.warning(friendly)

            # ------------------------------------------------------------------
            # Schedule display — structured table, sorted, with explanation.
            # ------------------------------------------------------------------
            if not plan:
                st.info(
                    "No tasks are due today or all tasks have already been completed."
                )
            else:
                # Time overrun check: mandatory tasks may exceed available time.
                total_minutes = sum(t.duration_minutes for t in plan)
                if total_minutes > owner.available_minutes_per_day:
                    overrun = total_minutes - owner.available_minutes_per_day
                    st.warning(
                        f"Your mandatory tasks alone require {total_minutes} minutes, "
                        f"but you have {owner.available_minutes_per_day} minutes available today. "
                        f"That is {overrun} minute(s) over your daily limit. "
                        f"Consider reducing a mandatory task's duration or increasing your available time."
                    )

                st.markdown(f"**Scheduled tasks — {total_minutes} min total**")

                # Cross-reference plan tasks back to their owning pets.
                all_pairs = scheduler._collect_all_tasks()
                id_to_pet = {id(task): pet for pet, task in all_pairs}

                # Build plan rows sorted by scheduled_time using sort_by_time().
                plan_pairs = [
                    (id_to_pet.get(id(task)), task) for task in plan
                ]
                # Filter out any pairs where pet lookup failed (should not occur).
                plan_pairs = [(pet, task) for pet, task in plan_pairs if pet is not None]
                plan_pairs_sorted = scheduler.sort_by_time(plan_pairs)

                # Append any tasks whose pet was not resolved (failsafe).
                resolved_ids = {id(task) for _pet, task in plan_pairs_sorted}
                for task in plan:
                    if id(task) not in resolved_ids:
                        plan_pairs_sorted.append((None, task))

                plan_rows = [
                    {
                        "Pet": pet.name if pet else "—",
                        "Task": task.name,
                        "Time": task.scheduled_time if task.scheduled_time else "unscheduled",
                        "Duration (min)": task.duration_minutes,
                        "Priority": task.priority,
                        "Mandatory": task.mandatory,
                    }
                    for pet, task in plan_pairs_sorted
                ]
                st.dataframe(plan_rows, use_container_width=True)

                # Full explain_plan output in an expander — clean by default.
                with st.expander("See full schedule explanation"):
                    explanation = scheduler.explain_plan(plan)
                    st.text(explanation)

                st.success(
                    f"Schedule generated: {len(plan)} task(s) planned, "
                    f"{total_minutes} of {owner.available_minutes_per_day} minutes used."
                )

        except Exception as e:
            st.error(f"Could not generate schedule: {e}")
