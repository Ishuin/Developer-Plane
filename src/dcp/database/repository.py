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

from dcp.core.models import Decision, Inference, Project, Signal

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

    def list_projects(
        self,
        limit: int = 25,
        offset: int = 0,
        search: Optional[str] = None,
        project_type: Optional[str] = None,
    ) -> Tuple[List[Project], int]:
        where, params = self._project_filter(search, project_type)
        rows = self._query(
            f"SELECT * FROM projects {where} ORDER BY path LIMIT ? OFFSET ?",  # noqa: S608
            tuple(params + [limit, offset]),
        )
        total = self._query(
            f"SELECT COUNT(*) AS n FROM projects {where}",  # noqa: S608
            tuple(params),
        )[0]["n"]
        return [Project(**dict(r)) for r in rows], total

    def get_project(self, path: str) -> Optional[Project]:
        rows = self._query("SELECT * FROM projects WHERE path = ?", (path,))
        return Project(**dict(rows[0])) if rows else None

    def clear_projects(self) -> int:
        """Empty the projects projection (the event log stays intact)."""
        cur = self._execute("DELETE FROM projects")
        return cur.rowcount

    def project_types(self) -> List[str]:
        rows = self._query("SELECT DISTINCT type FROM projects ORDER BY type")
        return [r["type"] for r in rows]

    @staticmethod
    def _project_filter(
        search: Optional[str], project_type: Optional[str]
    ) -> Tuple[str, List[Any]]:
        clauses, params = [], []
        if search:
            clauses.append("path LIKE ?")
            params.append(f"%{search}%")
        if project_type:
            clauses.append("type = ?")
            params.append(project_type)
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
