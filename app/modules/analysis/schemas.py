"""Analysis request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.analysis.prompts import ANALYSIS_LABELS


class AnalysisRequest(BaseModel):
    query: str = Field(min_length=1)
    analysis_type: str = "synthese_executive"
    title: str | None = None
    top_k: int = Field(default=8, ge=0, le=30)


class AnalysisResponse(BaseModel):
    analysis_type: str
    title: str
    content: str
    report_id: str | None = None  # rapport archivé automatiquement
    sources: list[dict]
    degraded: bool  # True if the primary web-search engine was unavailable
    status_note: str | None  # human-readable explanation when degraded
    metadata: dict


def available_types() -> list[dict]:
    return [{"key": k, "label": v} for k, v in ANALYSIS_LABELS.items()]
