"""Grounding: merge web results + internal passages into ONE ranked, numbered pool.

Both the chat and the report pipelines need the same thing: a single block of
numbered sources where web and internal material compete on relevance, and a
citations list that maps 1:1 to the [N] markers the model emits.

Keeping this in one place is not cosmetic — the report path previously numbered
web sources and RAG passages *separately*, so a [3] in the text could point at
a web source while meaning an internal document, and internal documents never
appeared in the report's source list at all.

Relevance is arbitrated by the reranker, not by an arbitrary cap: retrieval can
hand over as many internal passages as it finds, and weak ones simply lose their
place in the ranking.
"""
from __future__ import annotations


def assemble(query: str, web_results, doc_passages, top_k: int = 8,
             start_at: int = 1):
    """Return (context_block, citations) — both derived from one ordering."""
    from app.shared import search as web_search

    pool: list[dict] = []
    for r in web_results:
        pool.append({
            "text": f"{r.title}\n{r.snippet}",
            "tag": f"(web : {r.domain})" if r.domain else "(web)",
            "body": r.snippet or r.title,
            "cite": {"title": r.title, "url": r.url, "domain": r.domain, "source": "web",
                     "excerpt": (r.snippet or "")[:350]},
            "key": f"web::{r.domain}::{r.title.strip().lower()}",
        })
    for p in doc_passages:
        if p.source not in ("kb", "user", "notion"):
            continue
        meta = p.meta or {}
        title = meta.get("title") or meta.get("filename") or "Base de connaissance"
        ref = meta.get("source") or meta.get("category") or ""
        espace = p.source == "notion"
        pool.append({
            "text": p.text,
            "tag": (f"(espace Notion : {title})" if espace
                    else (f"(réf. interne : {ref} — {title})" if ref
                          else f"(réf. interne : {title})")),
            "body": p.text,
            "cite": {"title": title,
                     "source": "notion" if espace else ("interne" if p.source == "kb" else "document"),
                     "url": meta.get("url") if espace else None,
                     "reference": "Votre espace Notion" if espace else ref,
                     "excerpt": (p.text or "")[:350]},
            # Passages from the same document are distinct evidence: key on the
            # text, not the filename, or a long document collapses to one entry.
            "key": f"doc::{title}::{(p.text or '')[:80].strip().lower()}",
        })
    if not pool:
        return "", []

    order = web_search.rerank_indices(query, [it["text"] for it in pool], top_k)
    ranked = [pool[i] for i, _ in order] or pool[:top_k]

    # Dedupe FIRST, then number — so the inline [N] markers the model emits from
    # the numbered context map 1:1 to the citations list the user sees.
    deduped: list[dict] = []
    seen: set[str] = set()
    for it in ranked:
        if it["key"] in seen:
            continue
        seen.add(it["key"])
        deduped.append(it)

    lines = [f"[{n}] {it['tag']} {it['body']}"
             for n, it in enumerate(deduped, start_at)]
    citations = [it["cite"] for it in deduped]
    return "\n\n".join(lines), citations
