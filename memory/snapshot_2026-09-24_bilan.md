# Snapshot 24/09/2026 — bilan complet (sans parcours rejoué)

## Verdict
Plateforme saine côté services, parité, infra, KB (43 188 points / 148 docs intacts).
Un vrai bug trouvé : le **rapport offert échoue dans le worker** depuis le 18/09
(« could not find table 'projects' » : le worker n'importait pas le modèle
intelligence). Deux utilisatrices réelles sans rapport offert : iasi
(isaiaebongue@icloud.com, 21/09) et STARTZUP (lenamendy06@gmail.com, 16/09,
cause non retrouvée, journal purgé). Correctif commité 8ae0670 + test de
régression, NON déployé (rsync refusé par le classifieur).

## Chiffres (20/09 → 24/09)
- 2 comptes créés (iasi : migrée, 5 rapports d'avril restaurés, 130 crédits ;
  arthur.cotten@skema.edu : 100 crédits, aucune action).
- 7 j : 4 rapports terminés, 10 messages, 21 veilles ; coût modèle ≈ 1,8 €.
- Tavily toujours à quota (64 avertissements), cascade Exa/Linkup/Perplexity OK.
- henry.tran@hec.edu : 3 connexions refusées le 21/09 08:06, aucun compte à
  cette adresse ni à lumierequantum.com → il n'est pas inscrit.
- Redémarrage 23/09 06:12 = unattended-upgrade + needrestart (noyau 6.8.0-142,
  rsyslog). Risque : redémarrage pendant un rapport en cours.

## À faire
1. Déployer 8ae0670 (rsync + test + restart worker hors rapport en cours).
2. Ré-offrir le rapport à iasi et STARTZUP : supprimer leur marqueur
   `premier_rapport_offert` puis laisser le job de :40 les rattraper (envoie
   un email « rapport prêt » : OK de Miradie).
3. Exclure axial-* de needrestart (`/etc/needrestart/conf.d/axial.conf`).
4. Fichier parasite à la racine du dépôt (« = service.create_watch… », 25/08) à supprimer.
5. Tavily : décision plan ; GA4/Clarity : identifiants ; CREDITS_ESSAI.
