"""Analysis service — the single entry point to "run the algo".

`run_analysis()` is the one function that produces a report. It is deliberately
**resilient**: every external dependency (RAG, web-search, enrichment) is
best-effort. If the primary web-search engine is down (e.g. Perplexity quota),
the call does NOT crash — it returns a clear `degraded` result with a readable
status note, instead of the cryptic fallback the legacy system produced.

`stream_analysis()` wraps the same logic in Server-Sent Events with progress.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, field

from app.modules.analysis.prompts import (
    SYSTEM_PROMPT,
    get_prompt_template,
    is_valid_type,
    angles_de_recherche,
    sources_for,
)
from app.errors import AppError
from app.shared import llm_client

logger = logging.getLogger("axial.analysis")

# Cadence des battements de cœur SSE pendant la génération (secondes).
HEARTBEAT_SECONDS = 8

# Type d'analyse adossé à la base investisseurs plutôt qu'à la recherche web.
INVESTOR_MAPPING = "cartographie_investisseurs"


def _canonical_type(analysis_type: str) -> str:
    from app.modules.analysis.prompts import _canonical

    return _canonical(analysis_type)


@dataclass
class AnalysisResult:
    analysis_type: str
    title: str
    content: str
    sources: list[dict] = field(default_factory=list)
    degraded: bool = False
    status_note: str | None = None
    metadata: dict = field(default_factory=dict)


def _retrieve_context(query: str, user_id: str, top_k: int):
    """RAG retrieval — best-effort. Returns (context_str, passages)."""
    if top_k <= 0:
        return "", []
    try:
        from app.modules.rag import service as rag

        passages = rag.retrieve(query, user_id=user_id, top_k=top_k)
        return rag.format_context(passages), passages
    except Exception as e:  # embeddings/qdrant unavailable → continue without RAG
        logger.warning("RAG retrieval skipped: %s", e)
        return "", []


def run_analysis(*, query: str, analysis_type: str, user_id: str,
                 title: str | None = None, top_k: int | None = None,
                 company_context: str = "", tier: str = "report",
                 profile: dict | None = None,
                 db_pour_notion=None) -> AnalysisResult:
    if not is_valid_type(analysis_type):
        raise AppError(f"Type d'analyse inconnu : {analysis_type}", 400,
                       code="unknown_analysis_type")

    # Le type d'analyse commande le volume de sources (40 pour une synthèse
    # exécutive, 25 pour une veille) — la directive et le pipeline restent alignés.
    top_k = top_k or sources_for(analysis_type)

    label_title = title or analysis_type.replace("_", " ").title()

    # 1. External grounding: multi-provider web search (Exa+Tavily+Linkup) + rerank.
    from app.shared import search as web_search

    try:
        # Recherche multi-angles : la question de l'utilisateur, plus un angle
        # par axe de la directive. Une requête unique ne ramenait qu'une facette
        # du sujet, et ce que la recherche ne trouvait pas finissait comblé par
        # extrapolation dans le rapport.
        angles = angles_de_recherche(analysis_type, query)
        web_results = web_search.search_multi(angles, top_k=top_k,
                                              requete_de_rang=query)
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        web_results = []

    # 2. Internal grounding: RAG over the user's documents. No arbitrary cap —
    # retrieval hands over everything it finds and the reranker below arbitrates,
    # so a user with rich documents gets all of their relevant material.
    _, passages = _retrieve_context(query, user_id, top_k)

    # 3. ONE ranked, numbered pool: web and internal compete on relevance and the
    # [N] markers map 1:1 to the citations the reader sees (they used to be two
    # separate numberings colliding in the same prompt).
    from app.shared import grounding

    # Investor mapping is grounded FIRST on Axial's own investor database — that
    # verified data is the subject of the report; web results only add timing
    # context, and are numbered after so every [N] still maps to one citation.
    investor_context, investor_citations = "", []
    if _canonical_type(analysis_type) == INVESTOR_MAPPING:
        from app.modules.investors import service as investors

        mapping = None
        try:
            mapping = investors.map_for_profile(profile or {})
            investor_context = investors.format_context(mapping)
            investor_citations = investors.citations(mapping)
        except Exception as e:
            logger.warning("Investor mapping unavailable: %s", e)
        # Ce rapport N'EXISTE que par la base investisseurs : sans elle, mieux
        # vaut le dire et ne rien facturer qu'un texte adossé au web seul.
        if not investor_citations:
            reason = (mapping or {}).get("note") if mapping else None
            return AnalysisResult(
                analysis_type=analysis_type, title=label_title,
                content=("⚠️ La cartographie des investisseurs n'a pas pu être "
                         "produite. " + (reason or "La base investisseurs est "
                         "momentanément indisponible.") + " Aucun crédit n'a été "
                         "débité."),
                degraded=True, status_note="investors_unavailable",
                metadata={"passages": len(passages), "web_sources": len(web_results)},
            )

    # Espace Notion de l'utilisateur : ses pages rejoignent le pool de sources.
    try:
        from app.modules.integrations import notion_context

        passages = list(passages) + notion_context.passages_pour(db_pour_notion, user_id, query) \
            if db_pour_notion is not None else list(passages)
    except Exception as e:  # noqa: BLE001
        logger.warning("Espace Notion indisponible : %s", e)

    context, citations = grounding.assemble(
        query, web_results, passages, top_k, start_at=len(investor_citations) + 1
    )
    if investor_context:
        context = investor_context + ("\n\n" + context if context else "")
        citations = investor_citations + citations
    prompt = get_prompt_template(analysis_type).format(context=context or "Aucun.")
    if company_context:
        prompt = f"{company_context}\n\n{prompt}"
    prompt = f"{prompt}\n\nQuestion de l'utilisateur : {query}"

    # PII guard: redact outbound payload per configured mode before it leaves.
    from app.modules.pii.client import guard_outbound

    prompt = guard_outbound(prompt)

    # 4. Two-tier synthesis (Gemini for chat/draft, Claude for final reports).
    if not llm_client.generation_available():
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=("⚠️ Aucun moteur de génération n'est disponible pour le moment. "
                     "Réessaie une fois le service rétabli."),
            degraded=True, status_note="llm_unavailable",
            metadata={"passages": len(passages), "web_sources": len(web_results)},
        )
    try:
        # Sonnet 5 : le thinking adaptatif se décompte de max_tokens — un budget
        # trop court peut être entièrement consommé en réflexion (texte vide).
        from app.shared import langue as lg

        result = llm_client.generate(system=SYSTEM_PROMPT + lg.consigne_miroir(),
                                     prompt=prompt, tier=tier, max_tokens=32000)
    except Exception as e:
        logger.warning("Generation failed: %s", e)
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=f"⚠️ La génération a échoué ({type(e).__name__}). Réessaie dans un instant.",
            degraded=True, status_note="generation_failed",
            metadata={"passages": len(passages), "web_sources": len(web_results)},
        )

    if not (result.text or "").strip():
        logger.warning("Génération vide (thinking a consommé le budget ?) — modèle %s",
                       result.model)
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=("⚠️ La génération n'a pas abouti. Réessaie dans un instant — "
                     "aucun crédit n'a été débité."),
            degraded=True, status_note="empty_generation",
            metadata={"passages": len(passages), "web_sources": len(web_results)},
        )

    # Dernier filet : si le texte reste tronqué après les reprises automatiques,
    # on ne livre pas un document coupé en plein mot comme s'il était terminé.
    # Le crédit n'est pas débité — l'utilisateur n'a pas reçu ce qu'il a demandé.
    if result.stop_reason == "max_tokens":
        logger.warning("Rapport encore tronqué après reprises — type %s, modèle %s, "
                       "%d caractères produits", analysis_type, result.model,
                       len(result.text or ""))
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=(result.text or "") + (
                "\n\n---\n\n⚠️ **Ce rapport est incomplet.** La rédaction a atteint "
                "la limite de sortie du modèle avant sa conclusion. Aucun crédit "
                "n'a été débité — relance la génération."),
            sources=citations, degraded=True, status_note="truncated_generation",
            metadata={"passages": len(passages), "web_sources": len(web_results),
                      "stop_reason": result.stop_reason},
        )

    sources = citations
    return AnalysisResult(
        analysis_type=analysis_type,
        title=label_title,
        content=result.text,
        sources=sources,
        degraded=False,
        status_note=None,
        metadata={
            "passages": len(passages),
            "web_sources": len(web_results),
            "model": result.model,
            "provider": result.provider,
            "tier": tier,
            "tokens": result.tokens,
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


# --- Billing / persistence orchestration -----------------------------------

def precheck_credits(db, user_id: str, analysis_type: str, *, is_admin: bool) -> None:
    """Verify affordability BEFORE spending an API call. Admins bypass."""
    if is_admin:
        return
    from app.modules.billing import service as billing

    chk = billing.check_credits(db, user_id, analysis_type)
    if not chk["affordable"]:
        raise AppError(
            f"Crédits insuffisants ({chk['available']}/{chk['cost']}).",
            402, code="insufficient_credits",
        )


def finalize(db, user_id: str, analysis_type: str, result: AnalysisResult,
             *, is_admin: bool) -> dict:
    """After a successful analysis: charge, archive, track usage.

    Degraded results are NOT charged and NOT archived — the user got no value.
    """
    if result.degraded:
        return {"report_id": None, "charged": 0}

    from app.modules.analytics import client as analytics
    from app.modules.billing import service as billing
    from app.modules.reports import service as reports

    billing_res = billing.consume_credits(db, user_id, analysis_type, is_admin=is_admin)
    charged = billing_res.get("charged", 0)

    report = reports.create_report(
        db, user_id, title=result.title, content=result.content,
        analysis_type=analysis_type, sources=result.sources,
    )
    analytics.increment_usage(user_id, analyses=1, credits=charged, reports=1)

    result.metadata["report_id"] = str(report.id)
    result.metadata["charged"] = charged
    return {"report_id": str(report.id), "charged": charged}


# --- SSE streaming ---------------------------------------------------------

def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def stream_analysis(*, db, user_id: str, is_admin: bool, query: str,
                    analysis_type: str, title: str | None = None,
                    top_k: int | None = None):
    """Generator yielding SSE progress events, then a final `done` event.

    Bills only on success: credit check upfront, consume + archive + track after
    a non-degraded generation. Synchronous generator (FastAPI handles it).
    """
    yield _sse({"progress": 5, "step": "start", "message": "Démarrage de l'analyse…"})

    try:
        precheck_credits(db, user_id, analysis_type, is_admin=is_admin)
    except AppError as e:
        yield _sse({"step": "error", "done": True, "error": e.message,
                    "code": e.code})
        return

    yield _sse({"progress": 20, "step": "retrieve", "message": "Recherche documentaire…"})
    yield _sse({"progress": 40, "step": "generate",
                "message": "Génération du rapport (recherche web)…"})

    from app.modules.memory import service as memory

    company_context = memory.build_context(db, user_id)
    profile = _profile_dict(db, user_id)


    # La génération tourne dans un thread pendant que le flux continue d'émettre :
    # un rapport de fond prend plusieurs minutes, et une connexion silencieuse
    # est coupée par les proxys bien avant la fin.
    import concurrent.futures as _cf
    import time as _time

    def _produire_et_archiver() -> tuple[AnalysisResult, dict]:
        """Génère ET persiste, dans le thread, sur sa propre session.

        L'archivage vivait dans le générateur, après le dernier `yield`. Quand
        le navigateur se fermait pendant les minutes de rédaction, FastAPI
        fermait le générateur : la génération allait au bout, le modèle était
        payé, et le rapport était jeté. Reproduit le 25/08.

        La session de la requête HTTP meurt avec elle : le thread ouvre la
        sienne, sinon l'écriture se ferait sur une connexion déjà refermée.
        """
        from app.db import SessionLocal

        with SessionLocal() as db_thread:
            res = run_analysis(
                query=query, analysis_type=analysis_type, user_id=user_id,
                title=title, top_k=top_k, company_context=company_context,
                profile=profile, db_pour_notion=db_thread,
            )
            if res.degraded:
                return res, {}
            return res, (finalize(db_thread, user_id, analysis_type, res,
                                  is_admin=is_admin) or {})

    with _cf.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_produire_et_archiver)
        waited, progress = 0, 40
        while not future.done():
            _time.sleep(1)
            waited += 1
            if waited % HEARTBEAT_SECONDS:
                continue
            progress = min(progress + 3, 85)
            yield _sse({"progress": progress, "step": "generate", "heartbeat": True,
                        "message": f"Rédaction en cours… ({waited // 60} min {waited % 60:02d} s)"})
        try:
            result, info = future.result()
        except AppError as e:
            yield _sse({"step": "error", "done": True, "error": e.message})
            return
        except Exception as e:
            logger.warning("Stream generation failed: %s", e)
            yield _sse({"step": "error", "done": True,
                        "error": "La génération a échoué. Réessaie dans un instant."})
            return

    if result.degraded:
        # No charge, no archive.
        yield _sse({"progress": 100, "step": "done", "done": True,
                    "degraded": True, "message": result.content,
                    "data": _result_payload(result)})
        return

    yield _sse({"progress": 90, "step": "finalize", "message": "Finalisation…"})
    payload = _result_payload(result)
    payload["report_id"] = info.get("report_id")
    yield _sse({"progress": 100, "step": "done", "done": True, "data": payload})


def _result_payload(result: AnalysisResult) -> dict:
    return {
        "analysis_type": result.analysis_type,
        "title": result.title,
        "content": result.content,
        "sources": result.sources,
        "degraded": result.degraded,
        "status_note": result.status_note,
        "metadata": result.metadata,
    }


def _profile_dict(db, user_id: str) -> dict:
    """Company profile as a plain dict — what the investor mapping matches on."""
    from app.modules.memory import service as memory

    p = memory.get_profile(db, user_id)
    if p is None:
        return {}
    return {
        "sector": p.sector, "funding_stage": p.funding_stage,
        "target_market": p.target_market, "country": getattr(p, "country", None),
        "company_name": p.company_name,
    }
