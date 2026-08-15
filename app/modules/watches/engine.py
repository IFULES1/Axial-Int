"""Veille generation engine — cumulative, skill-driven monitoring.

Given a watch's skill, its rolling memory, and the fresh sources (RSS + web),
produce three things in one pass: the DELTA (what's new since last run), a
refreshed FULL report, and an updated rolling_state to carry into the next run.
The rolling memory is what makes the veille cumulative instead of amnesiac.
"""
from __future__ import annotations

import logging

from app.modules.watches.skills import VeilleSkill

logger = logging.getLogger("axial.watches.engine")

MAX_SOURCES = 12


def _format_sources(query: str, articles: list[dict], web_results: list) -> tuple[str, list[dict]]:
    """Merge RSS articles + web results into one block ranked by relevance to the
    watch's SUBJECT (not a generic query) — critical when broad feeds flood the
    pool with off-topic global news."""
    from app.shared import search as web_search

    pool: list[dict] = []
    for a in articles:
        pool.append({
            "text": f"{a.get('title', '')}\n{a.get('summary', '')}",
            "line": f"(RSS · {a.get('source', '')}) {a.get('title', '')} — {a.get('summary', '')}",
            "cite": {"title": a.get("title", ""), "url": a.get("url", ""),
                     "source": "rss", "published": a.get("published")},
        })
    for r in web_results:
        pool.append({
            "text": f"{r.title}\n{r.snippet}",
            "line": f"(web · {r.domain}) {r.title} — {r.snippet}",
            "cite": {"title": r.title, "url": r.url, "domain": r.domain, "source": "web"},
        })
    if not pool:
        return "", []

    order = web_search.rerank_indices(query, [p["text"] for p in pool], MAX_SOURCES)
    ranked = [pool[i] for i, _ in order] or pool[:MAX_SOURCES]
    lines = [f"[{n}] {it['line']}" for n, it in enumerate(ranked, 1)]
    citations = [it["cite"] for it in ranked]
    return "\n\n".join(lines), citations


_OUTPUT_INSTRUCTION = (
    "Structure ta réponse EXACTEMENT avec ces quatre marqueurs sur leur propre ligne, "
    "dans cet ordre, et rien avant le premier marqueur. Le contenu de chaque section est "
    "du markdown libre (retours à la ligne, titres, puces autorisés).\n\n"
    "===HAD_CHANGES===\n"
    "oui   (ou 'non' s'il n'y a aucune nouveauté significative depuis la dernière veille)\n"
    "===DELTA===\n"
    "Les NOUVEAUTÉS et évolutions depuis la dernière veille, en signaux datés et sourcés [n]. "
    "Au premier run, tout est nouveau. Concis.\n"
    "===FULL_REPORT===\n"
    "Le point COMPLET et actualisé sur le sujet, autonome et structuré (titres, puces), "
    "intégrant le nouveau ET l'acquis, sourcé [n]. Obligatoire même au premier run.\n"
    "===ROLLING_STATE===\n"
    "Résumé compact et factuel de tout ce que tu sais à ce stade, à réutiliser au prochain "
    "run (~400 mots max)."
)


def _section(text: str, marker: str, nexts: list[str]) -> str:
    """Extract the content after `marker` up to the next marker (or end)."""
    i = text.find(marker)
    if i == -1:
        return ""
    start = i + len(marker)
    end = len(text)
    for nm in nexts:
        j = text.find(nm, start)
        if j != -1:
            end = min(end, j)
    return text[start:end].strip()


def _parse(text: str) -> dict:
    """Split the delimiter-structured output into its four sections. Robust to
    markdown newlines that would break JSON. Falls back to whole-text-as-report."""
    s = text.strip()
    if "===DELTA===" not in s and "===FULL_REPORT===" not in s:
        return {"had_changes": True, "delta": "", "full_report": s, "rolling_state": None}
    had = _section(s, "===HAD_CHANGES===", ["===DELTA==="])
    return {
        "had_changes": not had.lower().startswith("non"),
        "delta": _section(s, "===DELTA===", ["===FULL_REPORT==="]),
        "full_report": _section(s, "===FULL_REPORT===", ["===ROLLING_STATE==="]),
        "rolling_state": _section(s, "===ROLLING_STATE===", []) or None,
    }


def generate_veille(*, skill: VeilleSkill, subject: str, rolling_state: str | None,
                    rss_articles: list[dict], web_results: list,
                    company_context: str) -> dict:
    """Run one cumulative veille pass. Returns
    {had_changes, delta, full_report, rolling_state, sources}."""
    from app.modules.pii.client import guard_outbound
    from app.shared import llm_client

    sources_block, citations = _format_sources(subject, rss_articles, web_results)
    memory = rolling_state or "Première veille sur ce sujet — aucun historique antérieur."

    parts = [
        f"Contexte entreprise :\n{company_context}" if company_context else "",
        f"Mémoire de veille (état roulant — ce que tu sais déjà des runs précédents) :\n{memory}",
        f"Nouvelles sources depuis la dernière veille (classées par pertinence) :\n{sources_block}"
        if sources_block else "Aucune source nouvelle n'a été récupérée pour ce run.",
        f"Sujet surveillé : {subject}",
        _OUTPUT_INSTRUCTION,
    ]
    prompt = guard_outbound("\n\n".join(p for p in parts if p))

    result = llm_client.generate(system=skill.system_prompt, prompt=prompt,
                                 tier="report", max_tokens=6000)
    parsed = _parse(result.text)
    # Robustness: never let a run land with an empty full report. On the first
    # pass (or if the model under-fills one field), mirror delta ↔ full_report.
    delta = (parsed.get("delta") or "").strip()
    full = (parsed.get("full_report") or "").strip()
    parsed["full_report"] = full or delta
    parsed["delta"] = delta or full
    parsed["sources"] = citations
    return parsed
