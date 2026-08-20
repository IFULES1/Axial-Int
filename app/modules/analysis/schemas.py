"""Analysis request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.modules.analysis.prompts import ANALYSIS_LABELS


class AnalysisRequest(BaseModel):
    query: str = Field(min_length=1)
    analysis_type: str = "synthese_executive"
    title: str | None = None
    # None = le nombre de sources est décidé par le type d'analyse (la directive
    # exige 25 à 40 sources selon le rapport ; cf. prompts.sources_for).
    top_k: int | None = Field(default=None, ge=0, le=60)


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
