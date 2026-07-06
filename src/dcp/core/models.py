"""Domain models shared across all modules."""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Project(BaseModel):
    path: str
    type: str = "Unknown"
    discovered_at: Optional[str] = None
    last_activity: Optional[str] = None


class Signal(BaseModel):
    """A raw, deterministic fact (layer 1 of the data trinity)."""

    id: Optional[int] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    event_type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[str] = None


class Inference(BaseModel):
    """A probabilistic guess with a mandatory confidence score (layer 2)."""

    id: Optional[int] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    inference_type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[str] = None
    confidence_score: float = Field(ge=0.0, le=1.0)


class Decision(BaseModel):
    """A system action or trigger (layer 3)."""

    id: Optional[int] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    decision_type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[str] = None


class Genome(BaseModel):
    """The detected identity of a project: stack, conventions, git state."""

    path: str
    type: str = "Unknown"
    markers: List[str] = Field(default_factory=list)
    has_tests: bool = False
    has_ci: bool = False
    has_docs: bool = False
    has_dockerfile: bool = False
    git: Dict[str, Any] = Field(default_factory=dict)


class StageResult(BaseModel):
    project_id: str
    stage: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)


class Page(BaseModel, Generic[T]):
    """Standard pagination envelope for every list endpoint."""

    items: List[T]
    page: int
    page_size: int
    total: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.page_size))
