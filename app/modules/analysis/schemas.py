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
    # Spec §2 — reprises après un verdict « sources insuffisantes ».
    # `elargir` : angles de recherche supplémentaires, produits une fois.
    # `forcer` : générer malgré le verdict, avec la mention « couverture
    # partielle » sur le rapport.
    elargir: bool = False
    forcer: bool = False


# `AnalysisResponse` a disparu avec Task 2 : `POST /analysis/run` rend le même
# `ReportDetail` que `GET /reports/{id}`, pour que le front n'ait qu'une forme
# de rapport à connaître, quelle que soit la route qui l'a produit.


def available_types() -> list[dict]:
    return [{"key": k, "label": v} for k, v in ANALYSIS_LABELS.items()]
