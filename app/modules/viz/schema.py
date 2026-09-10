"""VizSpec v1 — le seul contrat entre le modèle et le moteur de visualisation.

Dix champs, une seule structure de données à la fois. Ce qui n'est pas ici
n'existe pas pour le modèle : il ne choisit ni les couleurs, ni les axes, ni
la bibliothèque. Il dit ce qu'il veut montrer et pourquoi.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Intent = Literal["domination", "classement", "comparaison", "repartition", "concentration",
                 "croissance", "evolution", "projection", "rupture", "entonnoir",
                 "positionnement", "pont"]
Kind = Literal["kpi", "bar", "bar_h", "line", "area", "donut", "stacked_bar",
               "scatter", "quadrant", "funnel", "waterfall"]


class Point1(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    value: float


class Point2(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    x: float
    y: float
    size: float | None = None


class Step(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    delta: float


class VizSpec(BaseModel):
    version: Literal["1"] = "1"
    intent: Intent
    kind: Kind | None = None
    title: str = Field(min_length=3, max_length=80)
    subtitle: str | None = Field(default=None, max_length=140)
    unit: str = Field(default="", max_length=8)
    series: list[Point1] | None = Field(default=None, min_length=2, max_length=20)
    points: list[Point2] | None = Field(default=None, min_length=4, max_length=40)
    axes: dict[str, str] | None = None  # {"x": "Revenu (M€)", "y": "Croissance (%)"}
    steps: list[Step] | None = Field(default=None, min_length=2, max_length=8)
    highlight: str | None = None
    sources: list[int] = Field(default_factory=list, max_length=8)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _une_seule_structure(self):
        n = sum(x is not None for x in (self.series, self.points, self.steps))
        if n != 1:
            raise ValueError("exactement une structure de données : series, points ou steps")
        if self.points is not None and not (self.axes and "x" in self.axes and "y" in self.axes):
            raise ValueError("points exige axes.x et axes.y")
        if self.highlight and self.series and self.highlight not in {p.label for p in self.series}:
            raise ValueError("highlight doit être un label de series")
        return self

    @property
    def n(self) -> int:
        return len(self.series or self.points or self.steps or [])
