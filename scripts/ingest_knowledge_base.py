"""Ingest data/knowledge_base/ into the shared Qdrant `knowledge_base` collection.

Extract → chunk → embed (Cohere) → upsert with metadata (category from folder,
+ optional manifest.csv for source/sector/year). Idempotent (stable point ids),
resilient (a file that fails extraction is logged and skipped).

    doppler run -- python scripts/ingest_knowledge_base.py [--limit N] [--category 06_...]

Run with the API backend stopped (embedded Qdrant is single-process).
"""
from __future__ import annotations

import argparse
import csv
import uuid
from pathlib import Path

from app.modules.documents.extract import chunk_text, extract_text
from app.modules.rag import embeddings, vector_store

KB = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"
SUPPORTED = {".pdf", ".txt", ".md"}


def load_manifest() -> dict[str, dict]:
    path = KB / "manifest.csv"
    out: dict[str, dict] = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fn = (row.get("fichier") or "").split("/")[-1].strip()
                if fn:
                    out[fn] = row
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max files scanned (0 = all)")
    ap.add_argument("--max-new", type=int, default=0, help="stop after N newly-ingested docs (0 = no cap)")
    ap.add_argument("--category", default="", help="only this category folder")
    args = ap.parse_args()

    manifest = load_manifest()
    files = sorted(
        p for p in KB.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED
        and (not args.category or args.category in p.parts)
    )
    if args.limit:
        files = files[: args.limit]

    print(f"→ {len(files)} fichiers à ingérer\n")
    total_chunks, done, skipped = 0, 0, 0
    for p in files:
        category = next((part for part in p.parts if part[:2].isdigit()), "00")
        meta_row = manifest.get(p.name, {})
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(p)))
        if vector_store.has_document(doc_id, collection=vector_store.KB_COLLECTION):
            skipped += 1
            continue  # resume: already indexed
        try:
            text = extract_text(p.name, p.read_bytes())
            if not text or len(text) < 100:
                print(f"  ⚠️  skip (peu/pas de texte) : {p.name}")
                skipped += 1
                continue
            chunks = chunk_text(text)
            vectors = embeddings.embed_texts(chunks, input_type="search_document")
            payload = {
                "category": category,
                "title": meta_row.get("titre") or p.stem,
                "source": meta_row.get("source") or category,
                "sector": meta_row.get("secteur") or "",
                "filename": p.name,
            }
            n = vector_store.upsert_chunks(doc_id, "__kb__", chunks, vectors,
                                          collection=vector_store.KB_COLLECTION,
                                          extra_payload=payload)
            total_chunks += n
            done += 1
            print(f"  ✅ {category:26} {p.name[:52]:52} {n} chunks", flush=True)
            if args.max_new and done >= args.max_new:
                print(f"\n  ⏹  stop après {done} nouveaux docs (--max-new)")
                break
        except Exception as e:
            print(f"  ❌ {p.name[:52]:52} {type(e).__name__}: {str(e)[:60]}", flush=True)
            skipped += 1

    # Rough cost estimate: ~180 tokens/chunk × Cohere embed $0.12 / 1M tokens.
    est_tokens = total_chunks * 180
    est_cost = est_tokens / 1_000_000 * 0.12
    print(f"\n✅ Ingéré : {done} docs, {total_chunks} chunks | ⚠️ ignorés : {skipped}")
    print(f"💰 Coût estimé de ce batch : ~{est_tokens:,} tokens ≈ {est_cost:.3f} $ "
          f"(à comparer au dashboard Cohere)")
    try:
        vector_store._client().close()  # flush embedded Qdrant cleanly
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
