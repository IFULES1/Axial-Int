# Ciblage investisseurs v2 — spécification (18/09/2026)

Source : `2026-09-18-retours-workshop.md`, décisions de Miradie du 18/09.
Périmètre : quatre corrections ; les BA individuels et les bons interlocuteurs
par fonds sont des chantiers séparés.

## 1. Nombre d'investisseurs demandé (décision)

- `investors.service.nombre_demande(question) -> int | None` : lit « N
  investisseurs », « 5 à 10 investisseurs » (→ 10), « une dizaine » (10),
  « une vingtaine » (20), « top 15 », FR et EN ; `None` si rien.
- `map_for_profile(profile, limit=…)` reçoit `limit = N` si N est lu, sinon
  15 (comportement actuel). Fonds et réseaux comptent ensemble : la liste
  remise au modèle contient au plus N acteurs, composés selon §4.
- La directive `cartographie_investisseurs` reçoit une consigne construite
  par le moteur (pas un changement de texte figé) :
  - si `disponibles >= N` : « Le fondateur demande N investisseurs : présente
    exactement N acteurs, par ordre de priorité, tous issus des sources
    numérotées. »
  - si `disponibles < N` : « Le fondateur demande N investisseurs ; la base
    Axial n'en référence que `disponibles` qui correspondent à son secteur et
    à son stade. Présente-les tous et dis, dès l'introduction, que cette
    liste réunit l'exhaustivité et la pertinence de la base pour sa situation,
    sans compléter avec des noms venus du web. »
- `mapping["demande"] = {"n": N, "disponibles": total}` exposé dans
  `detail` du rapport pour le front (pastille « 8 sur 10 demandés »).

## 2. Attention au montant de la levée (décision)

- `investors.service.montant_de_levee(question) -> dict | None` :
  `{"montant_eur": int, "texte": "300 000k€", "lectures": [300_000_000, 300_000],
  "ambigu": bool}`. Règles : « 300 K€ », « 300k », « 1,5 M€ », « 2 millions »,
  « 500 000 € », « 300 000k€ » (ambigu : lu 300 M€ littéralement, 300 k€
  plausible) ; plausibilité par stade : pre-seed ≤ 2 M€, seed ≤ 8 M€, série A
  ≤ 30 M€ ; au-delà, `ambigu = True` avec la lecture plausible en second.
- Le moteur ajoute en tête du contexte investisseurs un bloc « Paramètres de
  la levée retenus : montant X € · stade Y » et, si ambigu, « Le montant écrit
  (« 300 000k€ ») se lit 300 M€ ; pour un pre-seed, 300 k€ est plus
  vraisemblable : le rapport retient 300 k€ et le signale. » La directive
  impose de restituer ces paramètres dans la première phrase de la synthèse.
- `detail["levee"] = {montant_eur, stade, ambigu, texte}` ; le front affiche
  un bandeau discret sous le titre du rapport « Montant retenu : 300 000 € ·
  pré-seed » (et « à vérifier » si ambigu) — clés i18n FR/EN.

## 3. Flux RSS visibles et testés (décision)

- Fiche d'un agent (carte dans la surface Agents) : liste des flux que
  l'agent lit, calculée par `GET /watches/{id}/feeds` → flux de l'utilisateur
  dont la catégorie ∈ `skill.rss_categories`, plus le catalogue de ces
  catégories ; chaque flux avec titre (ou URL), catégorie et `etat`
  (`ok` / `erreur`, dernière vérification). Bouton « Gérer mes flux » ouvrant
  la modale existante.
- Rattachement : `RssFeed.categories` inchangé ; à l'ajout d'une URL libre,
  le titre du flux est lu dans le XML (`<title>`) et enregistré.
- Test des flux : `scripts/tester_flux_rss.py` (dépôt) et `POST
  /watches/feeds/verifier` (admin) : pour chaque flux (utilisateurs +
  catalogue), un `GET` 10 s, parse, nombre d'entrées, date du plus récent ;
  résultat `{url, ok, statut_http, entrees, dernier, erreur}` ; `RssFeed.
  derniere_verification_at`, `derniere_erreur` (migration `0025_flux_rss`).
  Le catalogue (`data/rss_feeds.csv`) est corrigé : flux morts retirés ou
  remplacés.

## 4. Ciblage par stade (décision)

Composition de la liste remise au modèle, selon le stade du profil (ou de la
question s'il y est) :

| Stade | Composition (dans l'ordre) |
|---|---|
| idéation, pre-seed | réseaux de BA et plateformes d'amorçage d'abord ; puis fonds tagués pre-seed / amorçage ; consigne : mentionner le non dilutif (Bpifrance Bourse French Tech, prêts d'honneur, concours, aides régionales) comme premier levier |
| seed | réseaux de BA + fonds d'amorçage à parts égales |
| série A, B+ | fonds d'abord ; réseaux de BA seulement s'il reste de la place |

- `search()` garde son score ; `map_for_profile` compose `funds` / `networks`
  selon la table ci-dessus et respecte `limit` global (§1).
- « Déjà contactés » : `investors.service.deja_contactes(question) -> list[str]`
  (noms après « déjà contacté », « déjà identifié », « hors ») → retirés de la
  liste (correspondance insensible à la casse sur le nom de la société de
  gestion ou du réseau) et mentionnés dans le bloc de paramètres.
- Directive : consigne de composition par stade ajoutée dynamiquement (même
  mécanisme que §1), sans réécrire le texte existant.

## 5. Tests

Backend : `nombre_demande`, `montant_de_levee` (formats, ambiguïté,
plausibilité), `deja_contactes`, composition par stade (3 cas), limite
respectée, consigne dynamique dans le prompt (N ≥ et N >), `detail` exposé,
route `/watches/{id}/feeds`, vérification des flux (bouchonnée), titre lu à
l'ajout. Front (Node) : clés i18n FR/EN, bridge, carte d'agent appelle la
route. Registre : vouvoiement. Prompts figés inchangés hors ajouts
dynamiques.
