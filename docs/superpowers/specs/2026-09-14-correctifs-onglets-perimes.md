# Correctifs « onglets périmés » et revue de la liste maîtresse (14/09/2026)

Suite au retour de Miradie du 13/09 : « les boutons renommer / archiver des
conversations ne fonctionnent pas », « l'historique des rapports a disparu ».

## 1. Diagnostic

Les deux symptômes venaient d'onglets ouverts AVANT les déploiements du 11 et
du 13/09 : l'ancien bundle appelait l'API à l'ancienne (`GET /reports` sans
`limit`, `GET …/messages` sans `limit`) et recevait une page `{items,
has_more}` là où il attendait un tableau. Les journaux du 13/09 (06:30) le
montrent. Sur le bundle courant, renommer / épingler / archiver répondent 200
(vérifié avec le compte QA en prod) et les 8 rapports de Miradie sont en base.

## 2. Ce qui a été déployé le 14/09 (commits 0507517, 0b44564, 4510b22)

| Correctif | Où |
|---|---|
| Identifiant de build partagé entre `next build` (`generateBuildId`) et le bundle client (`env.NEXT_PUBLIC_BUILD_ID`), horodatage fixé par `npm run build` (`AXIAL_BUILD_ID`) | `frontend/next.config.mjs`, `frontend/package.json` |
| `GET /version` (Next, `no-store`) lit `.next/BUILD_ID` | `frontend/app/version/route.ts` |
| Veille côté client : démarrage, retour au premier plan, toutes les 10 min ; bandeau flottant « Une nouvelle version d'Axial est disponible · Recharger » sur TOUS les écrans (landing, connexion, onboarding, app). Pas de rechargement automatique : une réponse en flux serait coupée. | `frontend/app/_prototype/version.js` (module pur, 6 tests), `App.jsx`, `globals.css` |
| `GET /reports` sans `limit` rend à nouveau un tableau (forme héritée) ; avec `limit`, la page | `app/modules/reports/router.py` (+ test) |
| Stop d'un rapport relu toutes les 5 portions au lieu de 20 (latence ≈ 15 s au lieu d'≈ 1 min) ; balayage des titres garde son pas de 20 | `app/modules/analysis/service.py` |
| `aria-label` / `title` sur les deux boutons Retour sans texte de l'éditeur | `App.jsx` |
| Test `etapes.test.mjs` réparé (motif de polling élargi, cassé par 75e53fb) | `frontend/tests/etapes.test.mjs` |

Pièges rencontrés au déploiement, à retenir :
- `next start` ré-évalue `next.config.mjs` : un `Date.now()` dans la config
  donne un identifiant différent au serveur et au bundle → lire `.next/BUILD_ID`.
- `next build` évalue la config dans plusieurs processus : l'horodatage doit
  venir de l'environnement (`AXIAL_BUILD_ID=$(date +%s) next build`).
- Vérification de parité après build : `cat .next/BUILD_ID` =
  `grep -oh 'locale:"[a-z0-9-]*"' .next/static/chunks/*.js` = `curl /version`.

Limite : les onglets chargés avant le 14/09 n'ont pas la veille ; la forme
héritée de `GET /reports` et de `GET …/messages` les remet d'aplomb, mais un
rechargement manuel reste le geste sûr.

## 3. Inventaire des boutons (`2026-09-14-inventaire-boutons.md`)

Environ 165 éléments cliquables recensés, chaque `axXxx()` appelé existe dans
`bridge.js`, aucun `onClick` vide, aucun `disabled` figé. Seuls écarts :
- Documentation > Besoin d'aide : lien « support@axial.intelligence » en
  `href="#"` (FR et EN), adresse à confirmer — **sujet gardé ouvert par
  Miradie**, non modifié.
- Trois clés i18n « Connexion Google » jamais utilisées (code mort, pas un
  bouton visible).

## 4. Liste maîtresse — état

| Bloc | État |
|---|---|
| Front simplifié (historique, menu repliable, tuiles, abonnement, logo Notion, déconnexion) | en prod le 10/09 |
| Tiphanie admin + 200 crédits | fait le 11/09 |
| Conversations (crédits, contexte, documents, mémoire de fil, animation, solde, gestion, régénérer / éditer / stop, coût, mobile, markdown, erreurs, EN) et dette C.1–C.7 | en prod le 11/09 |
| Rapports v2 (suivi par id, Stop, sources insuffisantes, gestion, partage, comparaison, exports, dette 10–18, `/analysis/run`, Drive côté backend) | en prod le 13/09 |
| Onglets périmés, liste héritée, Stop réactif | en prod le 14/09 |
| Lien support de la Documentation | ouvert (Miradie) |
| Wording, prompts des rapports (tableaux / graphiques obligatoires sur les parties chiffrées), ressources CCI / INPI / Pépites | en attente de Miradie ; diff + OK avant déploiement |
| Sources de données par fonction (matrice type de rapport → fournisseurs / corpus) | à arbitrer avec Miradie |
| Recharge des API et revue de la stack pour septembre (consommation 30 jours, coût par fonction) | chantier à part, non commencé |
| Identifiants Google Cloud pour Drive | Miradie |
