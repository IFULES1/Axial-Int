# Snapshot — 2026-09-13

## Objectif de la session
Chantier « fonction par fonction » : Rapports v2 (spec, plan, 6 tâches SDD, revue globale, vague de correction), fusion, déploiement, parcours réel. Correctif Conversations : compatibilité des anciens onglets sur `/messages`.

## Tâches complétées
- [✓] Tiphanie : admin + 200 crédits ; son bug venait d'un onglet ouvert avant le déploiement (ancienne forme de `/messages`) → API rétro-compatible sans `limit` (1634650).
- [✓] Bilan Rapports (3 docs) + prompts extraits pour relecture (`docs/superpowers/specs/2026-09-12-prompts-rapports.md`).
- [✓] Rapports v2 en prod : voir `docs/superpowers/specs/2026-09-13-recap-rapports-v2.md`. Migration `0023_rapports_v2` (colonnes de suivi, partage, idempotence, `report_feedback`, index unique rapport offert, `legacy_verifie_at`).
- [✓] Prod : nginx 1800 s + buffering off sur `/api/`, `API_INTERNE_URL` dans `.env.local`, pool DB 10/20.

## Décisions
- `/analysis/run` = repli sur le même moteur suivi ; profondeur non branchée mais conservée ; « Étude personnalisée » inchangée (envoie `synthese_executive`) en attendant les prompts ; sources internes masquées à index constant sur la page publique ; Drive branché mais masqué sans identifiants Google.

## État
- `main` = 75e53fb, déployé. Tests : 402 pytest, 76 Node. Compte QA `qa-cv2-1109@axial-qa.fr` (162 crédits offerts).
- Wording global + prompts de rapport : toujours en attente de Miradie.

## Prochaines étapes
1. Recevoir les prompts retravaillés de Miradie → diff + OK → déploiement.
2. Identifiants Google Cloud pour Drive (Miradie), puis test de livraison.
3. Fonction suivante du chantier (Agents de veille ? Mémoire ? Crédits ?) à choisir avec Miradie.
4. Reliquats : latence du Stop (~1 min), aria-label du retour éditeur, comparaison à tester en prod.

## Contexte à ne pas oublier
- Déploiement : migration AVANT restart ; `rsync --files-from` ; vérifier bundle `127.0.0.1:8090` = 0 ; jamais `npm run build` pendant `next dev`.
- SDD : workspaces `.superpowers/sdd/<plan>/` (gitignorés) ; ledgers complets pour conversations-v2 et rapports-v2.
