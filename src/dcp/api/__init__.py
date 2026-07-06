"""FastAPI REST layer (thin — all logic lives in Sentry/Cortex modules)."""

from dcp.api.app import create_app

__all__ = ["create_app"]
