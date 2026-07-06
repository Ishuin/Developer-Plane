"""SQLite-backed event store implementing the Data Trinity.

Three append-only tables (raw_signals, inferences, decisions) plus one
projection table (projects) derived from ProjectDiscovered signals so
listings stay fast without replaying the log.
"""

import json
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dcp.core.models import AgentRun, Decision, Inference, Project, Signal, Task

_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    data TEXT NOT NULL,
    project_id TEXT
);
CREATE TABLE IF NOT EXISTS inferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    inference_type TEXT NOT NULL,
    data TEXT NOT NULL,
    project_id TEXT,
    confidence_score REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    data TEXT NOT NULL,
    project_id TEXT
);
CREATE TABLE IF NOT EXISTS projects (
    path TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'Unknown',
    discovered_at TEXT NOT NULL,
    last_activity TEXT
);
CREATE INDEX IF NOT EXISTS idx_signals_project ON raw_signals(project_id);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON raw_signals(timestamp);
CREATE INDEX IF NOT EXISTS idx_inferences_project ON inferences(project_id);
"""


class EventSourcingDB:
    """Thread-safe repository over the local Context Fabric database."""

    def __init__(self, db_path: str = "context_fabric.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Additive migrations for databases created by older versions."""
        for column, ddl in (
            ("status_headline", "ALTER TABLE projects ADD COLUMN status_headline TEXT"),
            ("status_health", "ALTER TABLE projects ADD COLUMN status_health TEXT"),
            ("analyzed_at", "ALTER TABLE projects ADD COLUMN analyzed_at TEXT"),
            ("completion_percent", "ALTER TABLE projects ADD COLUMN completion_percent REAL"),
            ("completion_source", "ALTER TABLE projects ADD COLUMN completion_source TEXT"),
            ("automation_enabled",
             "ALTER TABLE projects ADD COLUMN automation_enabled INTEGER NOT NULL DEFAULT 0"),
            ("kind", "ALTER TABLE projects ADD COLUMN kind TEXT"),
        ):
            try:
                self._execute(ddl)
            except sqlite3.OperationalError:
                pass  # column already exists
        self._execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'todo',
                pipeline TEXT NOT NULL DEFAULT 'project',
                origin TEXT DEFAULT '',
                run_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                exit_code INTEGER,
                task_brief TEXT,
                diff_stat TEXT,
                report TEXT,
                verdict TEXT
            )
        """)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _execute(self, sql: str, params: Tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _query(self, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # ---------------------------------------------------------------- signals
    def log_signal(
        self,
        event_type: str,
        data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Signal:
        signal = Signal(event_type=event_type, data=data, project_id=project_id)
        cur = self._execute(
            "INSERT INTO raw_signals (timestamp, event_type, data, project_id) "
            "VALUES (?, ?, ?, ?)",
            (signal.timestamp, signal.event_type, json.dumps(signal.data), project_id),
        )
        signal.id = cur.lastrowid
        return signal

    def get_signals(
        self,
        limit: int = 25,
        offset: int = 0,
        project_id: Optional[str] = None,
    ) -> List[Signal]:
        sql = "SELECT * FROM raw_signals"
        params: List[Any] = []
        if project_id:
            sql += " WHERE project_id = ?"
            params.append(project_id)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        return [self._row_to_signal(r) for r in self._query(sql, tuple(params))]

    def count_signals(self, project_id: Optional[str] = None) -> int:
        if project_id:
            rows = self._query(
                "SELECT COUNT(*) AS n FROM raw_signals WHERE project_id = ?",
                (project_id,),
            )
        else:
            rows = self._query("SELECT COUNT(*) AS n FROM raw_signals")
        return rows[0]["n"]

    # ------------------------------------------------------------- inferences
    def log_inference(
        self,
        inference_type: str,
        data: Dict[str, Any],
        confidence_score: float,
        project_id: Optional[str] = None,
    ) -> Inference:
        inference = Inference(
            inference_type=inference_type,
            data=data,
            project_id=project_id,
            confidence_score=confidence_score,
        )
        cur = self._execute(
            "INSERT INTO inferences "
            "(timestamp, inference_type, data, project_id, confidence_score) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                inference.timestamp,
                inference.inference_type,
                json.dumps(inference.data),
                project_id,
                inference.confidence_score,
            ),
        )
        inference.id = cur.lastrowid
        return inference

    def get_inferences(
        self,
        limit: int = 25,
        offset: int = 0,
        project_id: Optional[str] = None,
    ) -> List[Inference]:
        sql = "SELECT * FROM inferences"
        params: List[Any] = []
        if project_id:
            sql += " WHERE project_id = ?"
            params.append(project_id)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        return [self._row_to_inference(r) for r in self._query(sql, tuple(params))]

    def count_inferences(self, project_id: Optional[str] = None) -> int:
        if project_id:
            rows = self._query(
                "SELECT COUNT(*) AS n FROM inferences WHERE project_id = ?",
                (project_id,),
            )
        else:
            rows = self._query("SELECT COUNT(*) AS n FROM inferences")
        return rows[0]["n"]

    # -------------------------------------------------------------- decisions
    def log_decision(
        self,
        decision_type: str,
        data: Dict[str, Any],
        project_id: Optional[str] = None,
    ) -> Decision:
        decision = Decision(
            decision_type=decision_type, data=data, project_id=project_id
        )
        cur = self._execute(
            "INSERT INTO decisions (timestamp, decision_type, data, project_id) "
            "VALUES (?, ?, ?, ?)",
            (
                decision.timestamp,
                decision.decision_type,
                json.dumps(decision.data),
                project_id,
            ),
        )
        decision.id = cur.lastrowid
        return decision

    def get_decisions(
        self,
        limit: int = 25,
        offset: int = 0,
        project_id: Optional[str] = None,
    ) -> List[Decision]:
        sql = "SELECT * FROM decisions"
        params: List[Any] = []
        if project_id:
            sql += " WHERE project_id = ?"
            params.append(project_id)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        return [self._row_to_decision(r) for r in self._query(sql, tuple(params))]

    def count_decisions(self, project_id: Optional[str] = None) -> int:
        if project_id:
            rows = self._query(
                "SELECT COUNT(*) AS n FROM decisions WHERE project_id = ?",
                (project_id,),
            )
        else:
            rows = self._query("SELECT COUNT(*) AS n FROM decisions")
        return rows[0]["n"]

    # ------------------------------------------------------ projects (projection)
    def upsert_project(self, path: str, project_type: str) -> Project:
        now = datetime.now().isoformat()
        self._execute(
            "INSERT INTO projects (path, type, discovered_at, last_activity) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET type = excluded.type, "
            "last_activity = excluded.last_activity",
            (path, project_type, now, now),
        )
        return Project(path=path, type=project_type, discovered_at=now, last_activity=now)

    def touch_project(self, path: str) -> None:
        self._execute(
            "UPDATE projects SET last_activity = ? WHERE path = ?",
            (datetime.now().isoformat(), path),
        )

    # Whitelisted ORDER BY clauses — never interpolate user input directly.
    _PROJECT_SORTS = {
        "path": "path ASC",
        # Attention-first: red, yellow, green, then never-analyzed.
        "health": (
            "CASE status_health WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 "
            "WHEN 'green' THEN 2 ELSE 3 END ASC, path ASC"
        ),
        "activity": "last_activity DESC NULLS LAST, path ASC",
        "analyzed": "analyzed_at DESC NULLS LAST, path ASC",
    }

    def list_projects(
        self,
        limit: int = 25,
        offset: int = 0,
        search: Optional[str] = None,
        project_type: Optional[str] = None,
        health: Optional[str] = None,
        sort: str = "path",
    ) -> Tuple[List[Project], int]:
        where, params = self._project_filter(search, project_type, health)
        order = self._PROJECT_SORTS.get(sort, self._PROJECT_SORTS["path"])
        rows = self._query(
            f"SELECT * FROM projects {where} ORDER BY {order} LIMIT ? OFFSET ?",  # noqa: S608
            tuple(params + [limit, offset]),
        )
        total = self._query(
            f"SELECT COUNT(*) AS n FROM projects {where}",  # noqa: S608
            tuple(params),
        )[0]["n"]
        return [Project(**dict(r)) for r in rows], total

    def health_counts(self) -> Dict[str, int]:
        rows = self._query(
            "SELECT COALESCE(status_health, 'unanalyzed') AS h, COUNT(*) AS n "
            "FROM projects GROUP BY h"
        )
        return {r["h"]: r["n"] for r in rows}

    def get_project(self, path: str) -> Optional[Project]:
        rows = self._query("SELECT * FROM projects WHERE path = ?", (path,))
        return Project(**dict(rows[0])) if rows else None

    def set_project_status(
        self, path: str, headline: str, health: str
    ) -> None:
        self._execute(
            "UPDATE projects SET status_headline = ?, status_health = ?, "
            "analyzed_at = ? WHERE path = ?",
            (headline, health, datetime.now().isoformat(), path),
        )

    def set_project_completion(self, path: str, percent: float, source: str) -> None:
        self._execute(
            "UPDATE projects SET completion_percent = ?, completion_source = ? "
            "WHERE path = ?",
            (percent, source, path),
        )

    def set_automation(self, path: str, enabled: bool) -> None:
        self._execute(
            "UPDATE projects SET automation_enabled = ? WHERE path = ?",
            (1 if enabled else 0, path),
        )

    _QUEUE_ORDER = (
        "ORDER BY completion_percent DESC NULLS LAST, "
        "CASE status_health WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 "
        "WHEN 'green' THEN 2 ELSE 3 END ASC, path ASC LIMIT ?"
    )

    def autopilot_queue(self, limit: int = 50) -> List[Project]:
        """Automation-enabled projects, closest-to-done first, red tiebreak."""
        rows = self._query(
            f"SELECT * FROM projects WHERE automation_enabled = 1 {self._QUEUE_ORDER}",  # noqa: S608
            (limit,),
        )
        return [Project(**dict(r)) for r in rows]

    def ranked_projects(self, limit: int = 200) -> List[Project]:
        """Every project in completion-priority order (the score rank list)."""
        rows = self._query(
            f"SELECT * FROM projects {self._QUEUE_ORDER}",  # noqa: S608
            (limit,),
        )
        return [Project(**dict(r)) for r in rows]

    def set_project_kind(self, path: str, kind: str) -> None:
        self._execute(
            "UPDATE projects SET kind = ? WHERE path = ?", (kind, path)
        )

    # ----------------------------------------------------------------- tasks
    def insert_task(self, task: Task) -> Task:
        cur = self._execute(
            "INSERT INTO tasks (project_id, title, detail, status, pipeline, "
            "origin, run_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (task.project_id, task.title, task.detail, task.status,
             task.pipeline, task.origin, task.run_id,
             task.created_at, task.updated_at),
        )
        task.id = cur.lastrowid
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        rows = self._query("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return Task(**dict(rows[0])) if rows else None

    def list_tasks(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        pipeline: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Task]:
        sql, clauses, params = "SELECT * FROM tasks", [], []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if pipeline:
            clauses.append("pipeline = ?")
            params.append(pipeline)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        return [Task(**dict(r)) for r in self._query(sql, tuple(params))]

    def update_task(
        self, task_id: int, status: Optional[str] = None,
        run_id: Optional[int] = None,
    ) -> None:
        sets, params = ["updated_at = ?"], [datetime.now().isoformat()]
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if run_id is not None:
            sets.append("run_id = ?")
            params.append(run_id)
        params.append(task_id)
        self._execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            tuple(params),
        )

    def count_open_tasks(
        self, project_id: Optional[str] = None, pipeline: str = "project"
    ) -> int:
        sql = ("SELECT COUNT(*) AS n FROM tasks WHERE pipeline = ? "
               "AND status IN ('todo', 'in_progress', 'review')")
        params: List[Any] = [pipeline]
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        return self._query(sql, tuple(params))[0]["n"]

    # ------------------------------------------------------------ agent runs
    def insert_agent_run(self, run: AgentRun) -> AgentRun:
        cur = self._execute(
            "INSERT INTO agent_runs (project_id, started_at, finished_at, "
            "exit_code, task_brief, diff_stat, report, verdict) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run.project_id, run.started_at, run.finished_at, run.exit_code,
             run.task_brief, run.diff_stat, run.report, run.verdict),
        )
        run.id = cur.lastrowid
        return run

    def get_agent_runs(
        self, limit: int = 25, offset: int = 0,
        project_id: Optional[str] = None, pending_only: bool = False,
    ) -> List[AgentRun]:
        sql = "SELECT * FROM agent_runs"
        clauses, params = [], []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if pending_only:
            clauses.append("verdict IS NULL AND finished_at IS NOT NULL")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        return [AgentRun(**dict(r)) for r in self._query(sql, tuple(params))]

    def count_agent_runs(self, project_id: Optional[str] = None) -> int:
        if project_id:
            rows = self._query(
                "SELECT COUNT(*) AS n FROM agent_runs WHERE project_id = ?",
                (project_id,),
            )
        else:
            rows = self._query("SELECT COUNT(*) AS n FROM agent_runs")
        return rows[0]["n"]

    def get_agent_run(self, run_id: int) -> Optional[AgentRun]:
        rows = self._query("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
        return AgentRun(**dict(rows[0])) if rows else None

    def finish_agent_run(
        self, run_id: int, exit_code: int, diff_stat: str, report: str
    ) -> None:
        self._execute(
            "UPDATE agent_runs SET finished_at = ?, exit_code = ?, "
            "diff_stat = ?, report = ? WHERE id = ?",
            (datetime.now().isoformat(), exit_code, diff_stat, report, run_id),
        )

    def set_run_verdict(self, run_id: int, verdict: str) -> None:
        self._execute(
            "UPDATE agent_runs SET verdict = ? WHERE id = ?", (verdict, run_id)
        )

    def clear_projects(self) -> int:
        """Empty the projects projection (the event log stays intact)."""
        cur = self._execute("DELETE FROM projects")
        return cur.rowcount

    def project_types(self) -> List[str]:
        rows = self._query("SELECT DISTINCT type FROM projects ORDER BY type")
        return [r["type"] for r in rows]

    @staticmethod
    def _project_filter(
        search: Optional[str],
        project_type: Optional[str],
        health: Optional[str] = None,
    ) -> Tuple[str, List[Any]]:
        clauses, params = [], []
        if search:
            clauses.append("path LIKE ?")
            params.append(f"%{search}%")
        if project_type:
            clauses.append("type = ?")
            params.append(project_type)
        if health == "unanalyzed":
            clauses.append("status_health IS NULL")
        elif health:
            clauses.append("status_health = ?")
            params.append(health)
        return ("WHERE " + " AND ".join(clauses)) if clauses else "", params

    # ----------------------------------------------------------------- mapping
    @staticmethod
    def _row_to_signal(row: sqlite3.Row) -> Signal:
        return Signal(
            id=row["id"],
            timestamp=row["timestamp"],
            event_type=row["event_type"],
            data=json.loads(row["data"]),
            project_id=row["project_id"],
        )

    @staticmethod
    def _row_to_inference(row: sqlite3.Row) -> Inference:
        return Inference(
            id=row["id"],
            timestamp=row["timestamp"],
            inference_type=row["inference_type"],
            data=json.loads(row["data"]),
            project_id=row["project_id"],
            confidence_score=row["confidence_score"],
        )

    @staticmethod
    def _row_to_decision(row: sqlite3.Row) -> Decision:
        return Decision(
            id=row["id"],
            timestamp=row["timestamp"],
            decision_type=row["decision_type"],
            data=json.loads(row["data"]),
            project_id=row["project_id"],
        )
