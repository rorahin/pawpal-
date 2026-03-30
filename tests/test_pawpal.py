import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pawpal_system import Task, Pet


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
