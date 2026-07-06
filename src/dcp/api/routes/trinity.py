"""Data Trinity endpoints: raw signals, inferences, decisions (paginated)."""

from typing import Optional

from fastapi import APIRouter, Query, Request

from dcp.core.models import Decision, Inference, Page, Signal

router = APIRouter(prefix="/api", tags=["trinity"])


def _paging(request: Request, page: int, page_size: int):
    settings = request.app.state.dcp.settings
    if page_size <= 0:
        page_size = settings.default_page_size
    page_size = min(page_size, settings.max_page_size)
    return page_size, (page - 1) * page_size


@router.get("/signals", response_model=Page[Signal])
def signals(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(0, ge=0),
    project_id: Optional[str] = None,
):
    db = request.app.state.dcp.db
    limit, offset = _paging(request, page, page_size)
    return Page[Signal](
        items=db.get_signals(limit=limit, offset=offset, project_id=project_id),
        page=page, page_size=limit, total=db.count_signals(project_id),
    )


@router.get("/inferences", response_model=Page[Inference])
def inferences(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(0, ge=0),
    project_id: Optional[str] = None,
):
    db = request.app.state.dcp.db
    limit, offset = _paging(request, page, page_size)
    return Page[Inference](
        items=db.get_inferences(limit=limit, offset=offset, project_id=project_id),
        page=page, page_size=limit, total=db.count_inferences(project_id),
    )


@router.get("/decisions", response_model=Page[Decision])
def decisions(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(0, ge=0),
    project_id: Optional[str] = None,
):
    db = request.app.state.dcp.db
    limit, offset = _paging(request, page, page_size)
    return Page[Decision](
        items=db.get_decisions(limit=limit, offset=offset, project_id=project_id),
        page=page, page_size=limit, total=db.count_decisions(project_id),
    )
