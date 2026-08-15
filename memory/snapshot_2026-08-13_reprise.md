# Snapshot — 2026-08-13 (reprise) — chat branché + ingestion KB

## Objectif de la reprise
Terminer l'ingestion de la base de connaissance et brancher le chat Workspace au vrai moteur.

## Fait ce tour
- [✓] **KB partiellement indexée** : au check de reprise, `knowledge_base` = **6 756 points** (progression depuis les 1 173 du 1er run).
- [🔄] **Ingestion relancée** en tâche de fond (`scripts/ingest_knowledge_base.py`, reprenable — saute les docs déjà faits).
  Task background id `b7ltylxdm`. À la reprise : vérifier si terminée + compte final + docs échoués (PDF scannés → OCR plus tard).
- [✓] **Chat Workspace branché au backend** (frontend) :
  - `bridge.js` : ajout `axChat(text)` + `ensureConversation()` (crée/réutilise projet+conversation `/intelligence`).
  - `App.jsx` : import `axChat` ; `handleSendNew` et `handleSendInActive` rendus **async** → appellent `axChat`
    (placeholder « … » puis remplacé par la vraie réponse ; message d'erreur `⚠️` si échec). Plus de `makeFakeAiResponse`.
  - Le backend `post_message` est déjà aligné sur le nouveau moteur (recherche Exa/Tavily/Linkup + Gemini tier chat).

## ⚠️ NON ENCORE TESTÉ (à faire en priorité à la reprise)
Le chat branché **n'a pas pu être testé** : l'ingestion tient le verrou Qdrant embedded (mono-process),
donc impossible de lancer le backend en parallèle. **Test e2e à faire une fois l'ingestion finie.**

## Prochaines étapes (ordre)
1. Attendre/vérifier la **fin de l'ingestion** (notif task `b7ltylxdm`) → compte final KB.
   - Si ça re-429 : la clé Cohere est encore **trial** → passer en **payant** (`doppler secrets set COHERE_API_KEY`) puis relancer.
2. **Lancer le backend** : `doppler run -- .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090 --reload`.
3. **Lancer le front** : `cd frontend && doppler run -- npm run dev -- -p 3005`.
4. **Tester le chat à l'écran** : se connecter (founder2@axialtest.com / password123) → Workspace → poser une question →
   doit renvoyer une **vraie analyse sourcée** (web + base de connaissance). Vérifier lint front avant.
5. Lint/tests backend : `.venv/bin/ruff check app && .venv/bin/pytest -q`.

## Contexte à ne pas oublier
- **Doppler** = secrets. TOUT via `doppler run -- …`. Backend 8090, front 3005 (8080/3000 = ancien Docker, ne pas toucher).
- **Qdrant embedded mono-process** : NE PAS lancer backend + ingestion en même temps (verrou sur `data/qdrant`).
- **Décision embeddings B→C** notée dans `docs/PISTES_AMELIORATION.md` (rappel : bascule vers BGE-m3 auto-hébergé plus tard).
- Le cœur (search+LLM) est validé en réel ; reste à le voir tourner **depuis l'UI**.
- Snapshots clés : `snapshot_2026-08-13_coeur.md` (cœur marche), `snapshot_2026-08-13_19-00.md` (APIs+RAG+corpus), celui-ci (chat branché).
