"""End-to-end smoke test against the REAL app database (no Docker, no LLM keys).

Proves the migrated schema + core service logic work on actual PostgreSQL:
balance lifecycle, credit debit + report archival, memory context, vector store
(in-memory Qdrant), and watch scheduling. Run after `alembic upgrade head`.

    DATABASE_URL=postgresql+psycopg://... QDRANT_URL=:memory: python scripts/smoke.py
"""
from __future__ import annotations

import uuid

from app.db import SessionLocal
from app.modules.analysis.service import AnalysisResult, finalize
from app.modules.billing import service as billing
from app.modules.memory import service as memory
from app.modules.reports import service as reports
from app.modules.watches import service as watches


def main() -> int:
    user_id = str(uuid.uuid4())
    print(f"→ Utilisateur de test : {user_id}")

    with SessionLocal() as db:
        # 1. Balance lifecycle (Free Beta).
        bal = billing.get_or_create_balance(db, user_id)
        assert billing.available_credits(bal) == billing.FREE_BETA_CREDITS
        print(f"✓ Free Beta : {billing.available_credits(bal)} crédits")

        # 2. Memory profile + injected context.
        memory.upsert_profile(db, user_id, {"company_name": "Axial", "sector": "SaaS B2B",
                                            "funding_stage": "Seed"})
        assert memory.onboarding_complete(db, user_id)
        ctx = memory.build_context(db, user_id)
        assert "Axial" in ctx
        print("✓ Mémoire : profil créé, onboarding complet, contexte injectable")

        # 3. Successful analysis → charge + archive.
        result = AnalysisResult(analysis_type="etude_marche",
                                title="Étude de marché — test", content="# Rapport\n\nCorps.",
                                degraded=False, sources=[{"url": "https://insee.fr"}])
        info = finalize(db, user_id, "etude_marche", result, is_admin=False)
        assert info["charged"] == 40 and info["report_id"]
        bal = billing.get_or_create_balance(db, user_id)
        assert billing.available_credits(bal) == billing.FREE_BETA_CREDITS - 40
        print(f"✓ Analyse facturée 40 cr → solde {billing.available_credits(bal)}, "
              f"rapport {info['report_id'][:8]}…")

        # 4. Report persisted + PDF export.
        docs = reports.list_reports(db, user_id)
        assert len(docs) == 1
        pdf = reports.export_pdf(db, user_id, str(docs[0].id))
        assert pdf[:5] == b"%PDF-"
        print(f"✓ Rapport archivé + PDF généré ({len(pdf)} octets)")

        # 5. Vector store (in-memory Qdrant) upsert + search with fake vectors.
        from app.modules.rag import embeddings as emb
        from app.modules.rag import vector_store as vs
        dim = emb.embedding_dim()
        vs.upsert_chunks(str(uuid.uuid4()), user_id, ["chunk A", "chunk B"],
                         [[0.1] * dim, [0.2] * dim])
        hits = vs.search([0.1] * dim, user_id=user_id, top_k=2)
        assert hits and hits[0].text in {"chunk A", "chunk B"}
        print(f"✓ Qdrant in-memory : {len(hits)} passage(s) retrouvé(s)")

        # 6. Watch create + scheduling.
        w = watches.create_watch(db, user_id, name="Veille test", query="marché fintech",
                                 analysis_type="synthese_executive", cadence="weekly",
                                 email_recipients=None)
        assert w.next_run_at is not None
        print(f"✓ Veille créée, prochaine exécution : {w.next_run_at:%Y-%m-%d}")

    print("\n✅ SMOKE OK — schéma migré + services fonctionnent sur Postgres réel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
