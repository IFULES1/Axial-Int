"""Découpe un markdown de rapport en blocs typés.

Un seul analyseur pour le PDF (et demain pour tout autre rendu) : la logique
« qu'est-ce qu'un tableau » ne doit pas exister deux fois.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SEPARATEUR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")
# « Graphique : Parts de marché 2026 » / « Chart: Market share » — gras toléré.
_GRAPHIQUE = re.compile(r"^\s*\**\s*(?:graphique|chart)\s*:\s*(.+?)\s*\**\s*$", re.IGNORECASE)


@dataclass
class Bloc:
    genre: str
    texte: str = ""
    lignes: list[str] = field(default_factory=list)
    cellules: list[list[str]] = field(default_factory=list)
    # Rang d'apparition parmi les blocs de visualisation (```viz et
    # « Graphique : »), tous types confondus ; -1 pour les autres blocs. C'est
    # cet index qui relie un bloc du markdown à son rendu stocké.
    index: int = -1


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

    compteur_viz = 0
    i = 0
    while i < len(lignes):
        ligne = lignes[i].rstrip()
        if not ligne.strip():
            vider_puces()
            i += 1
            continue
        # Bloc fencé ```viz … ``` : la description JSON d'une visualisation
        # (VizSpec). Le contenu brut est gardé tel quel ; c'est le module viz
        # qui le valide et le compile.
        if ligne.strip().startswith("```viz"):
            vider_puces()
            j = i + 1
            contenu: list[str] = []
            while j < len(lignes) and not lignes[j].strip().startswith("```"):
                contenu.append(lignes[j])
                j += 1
            blocs.append(Bloc("viz", texte="\n".join(contenu).strip(), index=compteur_viz))
            compteur_viz += 1
            i = j + 1
            continue
        # « Graphique : <titre> » seul sur sa ligne, immédiatement suivi d'un
        # tableau : le modèle a jugé qu'un graphique parle mieux. Le bloc porte
        # le titre et les cellules ; le rendu décide de la forme finale.
        m_graph = _GRAPHIQUE.match(ligne)
        if m_graph:
            j = i + 1
            while j < len(lignes) and not lignes[j].strip():
                j += 1
            if j + 1 < len(lignes) and lignes[j].lstrip().startswith("|") \
                    and _SEPARATEUR.match(lignes[j + 1].strip()):
                vider_puces()
                cellules = [_cellules(lignes[j])]
                i = j + 2
                while i < len(lignes) and lignes[i].lstrip().startswith("|"):
                    cellules.append(_cellules(lignes[i]))
                    i += 1
                blocs.append(Bloc("graphique", texte=m_graph.group(1).strip(), cellules=cellules,
                                  index=compteur_viz))
                compteur_viz += 1
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


_NOMBRE = re.compile(r"^\s*([-+]?\d[\d\s  ]*(?:[.,]\d+)?)\s*(%|Md€|M€|k€|€|M\$|\$|k)?\s*$")


def serie_numerique(cellules: list[list[str]]):
    """Étiquettes + valeurs + unité, si et seulement si la 2e colonne est
    entièrement numérique et de même unité. Un graphique tracé sur des
    unités mélangées mentirait : mieux vaut aucun graphique."""
    if len(cellules) < 3 or any(len(ligne) < 2 for ligne in cellules):
        return None
    etiquettes, valeurs, unites = [], [], set()
    for ligne in cellules[1:]:
        m = _NOMBRE.match(ligne[1])
        if not m:
            return None
        brut = re.sub(r"[\s  ]", "", m.group(1)).replace(",", ".")
        valeurs.append(float(brut))
        unites.add(m.group(2) or "")
        etiquettes.append(ligne[0])
    if len(unites) != 1:
        return None
    return etiquettes, valeurs, unites.pop()
