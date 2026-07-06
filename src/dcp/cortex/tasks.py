"""Task board service: kanban cards that agents move automatically.

Lifecycle: todo → in_progress (agent picks up) → review (run finished)
→ done (run approved) / back to todo (run discarded). Users may discard
a card at any point — the emergency override.
"""

import logging
from typing import List, Optional

from dcp.core.models import Task
from dcp.database import EventSourcingDB

logger = logging.getLogger(__name__)

OPEN_STATUSES = ("todo", "in_progress", "review")
VALID_STATUSES = ("todo", "in_progress", "review", "done", "discarded")


class TaskService:
    def __init__(self, db: EventSourcingDB):
        self.db = db

    # ---------------------------------------------------------------- seeding
    def seed(
        self,
        project_id: str,
        titles: List[str],
        origin: str,
        pipeline: str = "project",
        detail: str = "",
    ) -> List[Task]:
        """Create tasks, skipping titles that already have an open card."""
        open_titles = {
            t.title for t in self.db.list_tasks(project_id=project_id, limit=500)
            if t.status in OPEN_STATUSES
        }
        created = []
        for title in titles:
            title = title.strip()
            if not title or title in open_titles:
                continue
            task = self.db.insert_task(Task(
                project_id=project_id, title=title[:200], detail=detail,
                pipeline=pipeline, origin=origin,
            ))
            created.append(task)
            open_titles.add(title)
        if created:
            self.db.log_decision(
                "TasksSeeded",
                {"count": len(created), "origin": origin, "pipeline": pipeline},
                project_id=project_id,
            )
        return created

    # ------------------------------------------------------------ transitions
    def move(self, task_id: int, status: str, run_id: Optional[int] = None,
             actor: str = "agent") -> Task:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        task = self.db.get_task(task_id)
        if task is None:
            raise KeyError(f"no such task: {task_id}")
        if task.status == "discarded":
            raise ValueError(f"task {task_id} is discarded")
        self.db.update_task(task_id, status=status, run_id=run_id)
        self.db.log_decision(
            "TaskMoved",
            {"task_id": task_id, "from": task.status, "to": status,
             "actor": actor},
            project_id=task.project_id,
        )
        return self.db.get_task(task_id)

    def discard(self, task_id: int) -> Task:
        """User emergency override: card leaves the board permanently."""
        task = self.db.get_task(task_id)
        if task is None:
            raise KeyError(f"no such task: {task_id}")
        self.db.update_task(task_id, status="discarded")
        self.db.log_decision(
            "TaskDiscarded", {"task_id": task_id, "actor": "user"},
            project_id=task.project_id,
        )
        return self.db.get_task(task_id)

    # ---------------------------------------------------------------- queries
    def board(self, project_id: Optional[str] = None,
              pipeline: str = "project") -> dict:
        tasks = self.db.list_tasks(project_id=project_id, pipeline=pipeline,
                                   limit=500)
        columns = {s: [] for s in ("todo", "in_progress", "review", "done")}
        for task in tasks:
            if task.status in columns:
                columns[task.status].append(task.model_dump())
        return columns

    def open_tasks(self, project_id: str, pipeline: str = "project",
                   limit: int = 5) -> List[Task]:
        return self.db.list_tasks(
            project_id=project_id, status="todo", pipeline=pipeline, limit=limit
        )
