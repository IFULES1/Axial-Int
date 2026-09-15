# Snapshot 2026-09-15 — Sources v2 en prod

## Fait
- Chantier Sources v2 exécuté en SDD (8 tâches, 1 revue par tâche, tours de
  correction, revue finale « déployable »), déployé le 15/09 au matin :
  contraintes de recherche (fraîcheur, domaines, pertinence), cascade à
  niveaux avec Perplexity, Pappers + sources par type de rapport, base
  investisseurs en conversation, base de connaissance admin (table
  `kb_documents`, migration 0024, écran Pilotage), Drive comme source
  (Picker), santé réelle des fournisseurs. Récap :
  `docs/superpowers/specs/2026-09-14-recap-sources-v2.md`.
- Base de connaissance nettoyée (128 hors sujet retirés) et enrichie (35
  documents officiels) : 148 documents, 43 188 vecteurs.
- Lien support branché ; prix en euros retirés des pastilles ; alerte email
  fournisseur ; bandeau de version ; menus réparés (14/09).

## Clés à poser par Miradie (sans elles, les fonctions restent masquées)
`PERPLEXITY_API_KEY`, `PAPPERS_API_KEY`, `GOOGLE_CLIENT_ID/SECRET` (Doppler),
`NEXT_PUBLIC_GOOGLE_API_KEY` + `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (`frontend/.env.local`,
puis rebuild du front). Vérifier ensuite avec `GET /health/providers?reel=1` (admin).

## Pièges appris
- Ne JAMAIS lancer la suite de tests sur le serveur sans Qdrant en mémoire :
  127 points de test ont pollué la base de prod le 15/09 (corrigé, conftest).
- `ingest_knowledge_base.py` identifie les documents par chemin ET par nom.
- Compte QA prod `qa-cv2-1109@axial-qa.fr` : mot de passe réinitialisé le
  15/09 (valeur dans le scratchpad de session, pas ici).

## Ouvert
- Décision sur les livres du commerce de la KB (« littérature stratégie »).
- Coût du rerank Cohere non compté (cascade). Bloc investisseurs seulement au
  message qui parle de levée. Prompts de rapport à améliorer (sujet ouvert).
- Next steps consommation / recharge : voir le message du 15/09.

## Complément 15/09 soir — Perplexity et Pappers en service
Clés posées ; tous fournisseurs verts au contrôle réel. Correctifs : sonde
réaliste, Perplexity limité à 2 appels simultanés + retry 429, extraction des
noms déterministe + JSON, homonymes Pappers, fiches gardées après classement,
verdict de couverture par préfixe (→ bandeau « Sources partielles » plus
fréquent : à revoir). Validation : étude de marché 45 sources dont 5 Pappers.
Démo le 16/09 : compte QA prod `qa-cv2-1109@axial-qa.fr`, 80 crédits restants.
