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
        st.success(f"{pet_name} added!")
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

if st.button("Add task"):
    if not owner.pets:
        st.warning("Add a pet first.")
    else:
        # Current UI supports one active pet; use the first registered pet.
        target_pet: Pet = owner.pets[0]
        try:
            new_task = Task(
                name=task_title,
                category="general",
                duration_minutes=int(duration),
                priority=priority,
            )
            target_pet.add_task(new_task)
            st.success(f"Task '{task_title}' added to {target_pet.name}!")
        except ValueError as e:
            st.error(str(e))

# Display the current task list for the first pet (if any).
if owner.pets:
    first_pet = owner.pets[0]
    if first_pet.tasks:
        st.markdown(f"**Current tasks for {first_pet.name}:**")
        task_rows = [
            {
                "Task": t.name,
                "Duration (min)": t.duration_minutes,
                "Priority": t.priority,
                "Mandatory": t.mandatory,
                "Completed": t.completed,
            }
            for t in first_pet.tasks
        ]
        st.table(task_rows)
    else:
        st.info(f"No tasks yet for {first_pet.name}. Add one above.")

st.divider()

# ---------------------------------------------------------------------------
# Section 4: Generate Schedule
# ---------------------------------------------------------------------------
st.subheader("Generate Schedule")

if st.button("Generate schedule"):
    # Guard: need at least one pet with at least one task.
    has_tasks = owner.pets and any(len(p.tasks) > 0 for p in owner.pets)
    if not owner.pets:
        st.warning("Add a pet first.")
    elif not has_tasks:
        st.warning("Add at least one task before generating a schedule.")
    else:
        try:
            scheduler = Scheduler(owner)
            plan = scheduler.generate_plan()
            explanation = scheduler.explain_plan(plan)
            st.markdown("```\n" + explanation + "\n```")
        except Exception as e:
            st.error(str(e))
