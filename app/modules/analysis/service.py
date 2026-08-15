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
)
from app.errors import AppError
from app.shared import llm_client

logger = logging.getLogger("axial.analysis")


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
                 title: str | None = None, top_k: int = 8,
                 company_context: str = "", tier: str = "report") -> AnalysisResult:
    if not is_valid_type(analysis_type):
        raise AppError(f"Type d'analyse inconnu : {analysis_type}", 400,
                       code="unknown_analysis_type")

    label_title = title or analysis_type.replace("_", " ").title()

    # 1. External grounding: multi-provider web search (Exa+Tavily+Linkup) + rerank.
    from app.shared import search as web_search

    try:
        web_results = web_search.search(query, top_k=top_k)
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        web_results = []
    web_context = web_search.format_sources(web_results)

    # 2. Internal grounding: RAG over the user's documents.
    rag_context, passages = _retrieve_context(query, user_id, top_k)

    # 3. Assemble context + prompt.
    context = "\n\n".join(c for c in (web_context, rag_context) if c) or "Aucun."
    prompt = get_prompt_template(analysis_type).format(context=context)
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
        result = llm_client.generate(system=SYSTEM_PROMPT, prompt=prompt,
                                     tier=tier, max_tokens=4000)
    except Exception as e:
        logger.warning("Generation failed: %s", e)
        return AnalysisResult(
            analysis_type=analysis_type, title=label_title,
            content=f"⚠️ La génération a échoué ({type(e).__name__}). Réessaie dans un instant.",
            degraded=True, status_note="generation_failed",
            metadata={"passages": len(passages), "web_sources": len(web_results)},
        )

    sources = [{"title": r.title, "url": r.url, "domain": r.domain,
                "provider": r.provider, "score": r.score} for r in web_results]
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
                    analysis_type: str, title: str | None = None, top_k: int = 8):
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
    try:
        result = run_analysis(query=query, analysis_type=analysis_type,
                              user_id=user_id, title=title, top_k=top_k,
                              company_context=company_context)
    except AppError as e:
        yield _sse({"step": "error", "done": True, "error": e.message})
        return

    if result.degraded:
        # No charge, no archive.
        yield _sse({"progress": 100, "step": "done", "done": True,
                    "degraded": True, "message": result.content,
                    "data": _result_payload(result)})
        return

    yield _sse({"progress": 90, "step": "finalize", "message": "Finalisation…"})
    finalize(db, user_id, analysis_type, result, is_admin=is_admin)
    yield _sse({"progress": 100, "step": "done", "done": True,
                "data": _result_payload(result)})


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
