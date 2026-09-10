"""Découpe un markdown de rapport en blocs typés.

Un seul analyseur pour le PDF (et demain pour tout autre rendu) : la logique
« qu'est-ce qu'un tableau » ne doit pas exister deux fois.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SEPARATEUR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")


@dataclass
class Bloc:
    genre: str
    texte: str = ""
    lignes: list[str] = field(default_factory=list)
    cellules: list[list[str]] = field(default_factory=list)


def _cellules(ligne: str) -> list[str]:
    ligne = ligne.strip()
    if ligne.startswith("|"):
        ligne = ligne[1:]
    if ligne.endswith("|"):
        ligne = ligne[:-1]
    return [c.strip() for c in ligne.split("|")]


def decouper(markdown: str) -> list[Bloc]:
    blocs: list[Bloc] = []
    puces: list[str] = []
    lignes = (markdown or "").splitlines()

    def vider_puces() -> None:
        if puces:
            blocs.append(Bloc("puces", lignes=list(puces)))
            puces.clear()

    i = 0
    while i < len(lignes):
        ligne = lignes[i].rstrip()
        if not ligne.strip():
            vider_puces()
            i += 1
            continue
        # Tableau : une ligne « | … | » suivie d'une ligne de séparation.
        if ligne.lstrip().startswith("|") and i + 1 < len(lignes) \
                and _SEPARATEUR.match(lignes[i + 1].strip()):
            vider_puces()
            cellules = [_cellules(ligne)]
            i += 2
            while i < len(lignes) and lignes[i].lstrip().startswith("|"):
                cellules.append(_cellules(lignes[i]))
                i += 1
            blocs.append(Bloc("tableau", cellules=cellules))
            continue
        if ligne.startswith("### "):
            vider_puces()
            blocs.append(Bloc("h3", texte=ligne[4:]))
        elif ligne.startswith("## "):
            vider_puces()
            blocs.append(Bloc("h2", texte=ligne[3:]))
        elif ligne.startswith("# "):
            vider_puces()
            blocs.append(Bloc("h1", texte=ligne[2:]))
        elif ligne.strip() in ("---", "***"):
            vider_puces()
            blocs.append(Bloc("hr"))
        elif re.match(r"^\s*[-*]\s+", ligne):
            puces.append(re.sub(r"^\s*[-*]\s+", "", ligne))
        else:
            vider_puces()
            blocs.append(Bloc("p", texte=ligne))
        i += 1
    vider_puces()
    return blocs
