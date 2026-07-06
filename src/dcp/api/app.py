"""FastAPI application factory."""

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dcp import __version__
from dcp.api.deps import AppState, build_state
from dcp.api.routes import (
    agents, analysis, autopilot, projects, tasks, trinity, watcher,
)
from dcp.config import Settings, get_settings


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state: AppState = build_state(settings)
        app.state.dcp = state
        roots = [r.strip() for r in settings.watch_roots.split(",") if r.strip()]
        valid_roots = [r for r in roots if os.path.isdir(r)]
        if valid_roots:
            state.watcher.start(valid_roots)
        state.self_improvement.start_scheduler()
        yield
        state.self_improvement.stop_scheduler()
        state.watcher.stop()
        state.db.close()

    app = FastAPI(
        title="Developer Control Plane",
        version=__version__,
        lifespan=lifespan,
    )

    app.include_router(projects.router)
    app.include_router(trinity.router)
    app.include_router(agents.router)
    app.include_router(analysis.router)
    app.include_router(autopilot.router)
    app.include_router(autopilot.completion_router)
    app.include_router(tasks.router)
    app.include_router(tasks.self_router)
    app.include_router(watcher.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": __version__}

    web_dir = settings.web_dir
    if web_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(str(web_dir / "index.html"))

    return app
