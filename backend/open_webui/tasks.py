# tasks.py
import asyncio
from typing import Dict, Optional
from uuid import uuid4

# A dictionary to keep track of active tasks
tasks: Dict[str, asyncio.Task] = {}
message_tasks: Dict[str, str] = {}
task_messages: Dict[str, str] = {}
message_task_users: Dict[str, str] = {}
pending_stop_tasks: Dict[str, str] = {}


def cleanup_task(task_id: str):
    """
    Remove a completed or canceled task from the global `tasks` dictionary.
    """
    tasks.pop(task_id, None)
    message_id = task_messages.pop(task_id, None)
    if message_id:
        if message_tasks.get(message_id) == task_id:
            message_tasks.pop(message_id, None)
        message_task_users.pop(message_id, None)


def create_task(
    coroutine,
    message_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """
    Create a new asyncio task and add it to the global task dictionary.
    """
    task_id = str(uuid4())  # Generate a unique ID for the task
    task = asyncio.create_task(coroutine)  # Create the task

    # Add a done callback for cleanup
    task.add_done_callback(lambda t: cleanup_task(task_id))

    tasks[task_id] = task

    if message_id:
        message_tasks[message_id] = task_id
        task_messages[task_id] = message_id
        if user_id:
            message_task_users[message_id] = user_id

        pending_user_id = pending_stop_tasks.pop(message_id, None)
        if pending_user_id and (not user_id or pending_user_id == user_id):
            task.cancel()

    return task_id, task


def get_task(task_id: str):
    """
    Retrieve a task by its task ID.
    """
    return tasks.get(task_id)


def list_tasks():
    """
    List all currently active task IDs.
    """
    return list(tasks.keys())


async def stop_task(task_id: str):
    """
    Cancel a running task and remove it from the global task list.
    """
    task = tasks.get(task_id)
    if not task:
        raise ValueError(f"Task with ID {task_id} not found.")

    task.cancel()  # Request task cancellation
    try:
        await task  # Wait for the task to handle the cancellation
    except asyncio.CancelledError:
        # Task successfully canceled
        tasks.pop(task_id, None)  # Remove it from the dictionary
        return {"status": True, "message": f"Task {task_id} successfully stopped."}

    return {"status": False, "message": f"Failed to stop task {task_id}."}


async def stop_task_by_message_id(message_id: str, user_id: Optional[str] = None):
    task_id = message_tasks.get(message_id)

    if not task_id:
        if user_id:
            pending_stop_tasks[message_id] = user_id
        return {"status": True, "message": f"Stop request accepted for message {message_id}."}

    owner_user_id = message_task_users.get(message_id)
    if user_id and owner_user_id and owner_user_id != user_id:
        raise ValueError(f"Task for message {message_id} not found.")

    return await stop_task(task_id)
