# Récap — Rapports v2 en production (13/09/2026)

## Ce qui a été livré (branche `rapports-v2`, 13 commits, fusionnée dans `main`)
- **Génération suivie par identifiant** : ligne `reports` créée au lancement (`statut`, `etape`, `progression`, `detail`), vraies étapes (sources trouvées, sélection, couverture, rédaction « section n/N », finalisation), chrono continu, Stop, reprise après rechargement (stockage local + polling 3 s), rapports « en cours » visibles dans la liste, débit et archivage dans une seule transaction, échéance 30 min, balayage des orphelins (démarrage + par compte), clé d'idempotence en colonne.
- **Aperçu des sources avant débit** : jugement de couverture (prompt interne court) → `sources_insuffisantes` sans débit, avec Reformuler / Recherche élargie / Générer quand même.
- **Dégradé et signalement** : bandeau par raison, formulaire d'avis dans l'app (`report_feedback`) avec email technique à Miradie ; le Google Form disparaît.
- **Gestion** : supprimer, renommer, épingler, archiver, dossiers partagés avec les conversations, recherche, pagination, coût (crédits · tokens), comparaison côte à côte, export PDF / Markdown / DOCX, partage public révocable (`/p/<pseudo>/<slug>-<jeton>`, sources internes masquées à index constant, graphiques accessibles par jeton), livraison Drive (tuile masquée sans identifiants Google), solde rafraîchi, écran crédits unique, feuille d'impression.
- **Dette** : rapport offert protégé par index unique, import hérité une seule fois, alias uniques, tarifs de recherche en configuration, images viz réservées au propriétaire / admin / jeton, `POST /reports` réservé admin, `/analysis/run` sur le même moteur, CSS de l'ancien éditeur retiré, pool DB configurable.

## Vérifié en production le 13/09 (compte QA)
| Test | Résultat |
|---|---|
| Question absurde | « Sources insuffisantes » en 30 s, 0 crédit, sources listées, 3 actions |
| Rapport concurrentiel | 30 sources → 29 retenues, section 1/7 → 7/7, terminé ~4 min, 25 crédits · 31 k tokens |
| Rechargement en cours de génération | reprise à l'étape exacte |
| Partage public | page servie, `noindex`, graphique chargé via jeton |
| Exports | md 33 Ko, docx 99 Ko, pdf 532 Ko |
| Signalement | 201, email parti |
| Renommer / épingler / archiver / supprimer | OK, sections Épinglés / Récents / Archivés |
| Stop | pris en compte entre deux étapes du modèle : ~1 min de latence, statut `annule`, 0 crédit |
| Mobile 375 px | voir ci-dessous |

## Corrigé pendant le parcours
- Solde non rafraîchi quand un rapport suivi par polling se termine (`75e53fb`).

## Reliquats / à savoir
- La latence du Stop dépend de la cadence des morceaux du modèle (contrôle tous les 20 morceaux) : jusqu'à ~1 min.
- Bouton « retour » de l'éditeur sans `aria-label`.
- Comparaison et livraison Drive non testées en prod (Drive : identifiants Google à créer par Miradie, procédure dans `docs/DEPLOY.md`).
- Prompts de rapport inchangés ; deux prompts internes nouveaux (couverture, recherche élargie) listés dans le contenu à valider.
- nginx : `proxy_read_timeout 1800s` + `proxy_buffering off` sur `/api/` ; `.env.local` : `API_INTERNE_URL=http://127.0.0.1:8090`.
