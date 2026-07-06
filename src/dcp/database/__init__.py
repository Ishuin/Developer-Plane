"""Persistence layer: append-only event log on SQLite (repository pattern)."""

from dcp.database.repository import EventSourcingDB

__all__ = ["EventSourcingDB"]
