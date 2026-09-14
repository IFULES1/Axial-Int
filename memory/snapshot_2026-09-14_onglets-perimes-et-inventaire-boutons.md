# Snapshot 2026-09-14 — onglets périmés corrigés, inventaire des boutons

## Contexte
Retour de Miradie du 13/09 : menus de conversation « inopérants », historique
des rapports « disparu », « assure-toi que tous les boutons fonctionnent ».
Cause : onglets chargés avant les déploiements du 11 et du 13/09 (ancien
bundle contre API nouvelle). Miradie a validé la vague 1 sauf le lien support
de la Documentation (gardé ouvert).

## Fait aujourd'hui (en prod, commits 0507517 → 4510b22)
- Détection de version : `GET /version` (Next, lit `.next/BUILD_ID`), veille
  client `frontend/app/_prototype/version.js`, bandeau « Recharger » sur tous
  les écrans. Horodatage fixé par `npm run build` (`AXIAL_BUILD_ID`).
- `GET /reports` sans `limit` = tableau hérité ; Stop relu toutes les 5 portions ;
  `aria-label` sur les Retour de l'éditeur ; test `etapes.test.mjs` réparé.
- Inventaire statique de ~165 éléments cliquables : tout branché sauf le lien
  support (`href="#"`, adresse `support@axial.intelligence` douteuse) et 3 clés
  i18n Google mortes. Détail : `docs/superpowers/specs/2026-09-14-inventaire-boutons.md`.
- Récap : `docs/superpowers/specs/2026-09-14-correctifs-onglets-perimes.md`.

- Menus ⋯ / Exporter / Livrer : les éléments ne répondaient pas (menu fermé au
  `mousedown` par l'écouteur du `document`, où Next monte React) → attribut
  `data-ax-menu` sur les menus, test `menus.test.mjs`, vérifié en prod.

## Pièges appris
- Un `stopPropagation` React ne bloque pas un écouteur natif posé sur
  `document` : sous Next (racine = `document`), garder les gardes par attribut.
- Vérifier la compilation locale avant tout `npm run build` en prod : un
  commentaire JSX mal placé a donné 3 minutes de 502.
- `next start` ré-évalue `next.config.mjs` ; `next build` l'évalue dans
  plusieurs processus : l'identifiant de build doit venir de l'environnement
  et le serveur doit lire `.next/BUILD_ID`. Vérifier la parité après build.
- Postgres local : verrou `postmaster.pid` périmé après redémarrage (PID
  réutilisé par un autre processus) → supprimer le fichier puis
  `brew services start postgresql@16`.
- Compte QA local : `qa-front-1009@axial-qa.fr` (mot de passe local réinitialisé
  le 14/09, base locale uniquement).

## Reste ouvert
- Lien support de la Documentation (adresse à donner par Miradie).
- Wording + prompts de rapport (tableaux / graphiques sur les parties
  chiffrées), ressources CCI / INPI / Pépites — diff + OK avant déploiement.
- Matrice sources par fonction ; revue de la stack API de septembre
  (consommation, coût par fonction, recharges) ; identifiants Google Cloud
  pour Drive ; test de la vue Comparer en prod.
