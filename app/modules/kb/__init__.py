"""Base de connaissance Axial — registre applicatif au-dessus de Qdrant.

Voir `docs/superpowers/specs/2026-09-14-sources-v2.md` §5. La collection
Qdrant `knowledge_base` (payload, chunking, embeddings) reste celle de
`scripts/ingest_knowledge_base.py` — ce module ajoute seulement la table
`kb_documents`, le service d'ingestion admin (fichier/URL) et les routes de
gestion (Pilotage).
"""
