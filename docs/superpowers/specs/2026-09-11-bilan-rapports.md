# Bilan « Rapports » — synthèse (11/09/2026)

Sources : exploration backend (`2026-09-11-bilan-rapports-backend.md`),
exploration frontend (`2026-09-11-bilan-rapports-frontend.md`), chiffres de
production et un rapport réel généré le 11/09 à 08h05 (compte QA, type
« Cartographie concurrentielle », 25 crédits).

---

## 1. Comment ça marche aujourd'hui

### Le parcours utilisateur
1. Menu « Rapports » → six tuiles (Étude de marché 40, Cartographie
   concurrentielle 25, Veille réglementaire 25, Analyse de risques 25,
   Cartographie investisseurs 30, Étude personnalisée 40), une zone de
   question, quatre exemples cliquables, la liste « Vos rapports ».
2. Garde de solde (écran `ReportsQuota`) puis « Lancer le rapport ».
3. Écran « Génération en cours » : trois étapes (sources, rédaction,
   finalisation), pourcentage et chrono, « Vous pouvez naviguer ailleurs ».
4. Éditeur : titre, nombre de sources, boutons PDF et « Votre avis »
   (lien vers un Google Form), document rendu (titres, tableaux,
   graphiques SVG, citations [N] cliquables, section Sources), livraison
   Notion si connecté.
5. À l'inscription : un **premier rapport offert** (étude de marché sur la
   question suggérée par le profil) est lancé en arrière-plan côté serveur,
   l'utilisateur reçoit un email quand il est prêt.

### L'architecture d'une génération (backend, `analysis/service.py`)
| Étape | Détail |
|---|---|
| Crédits | vérification avant tout appel, débit **après** succès seulement |
| Directive | 7 types fermés (`ANALYSIS_DIRECTIVES`) : volume cible, sources minimum, angles, consignes spéciales ; règles de style communes (synthèse exécutive en tête, tableaux, citations, blocs viz, vouvoiement) |
| Recherche | multi-angles (question + un angle par axe), 3 fournisseurs web (Exa, Tavily, Linkup) + RAG documents + Notion, rerank Cohere ; jusqu'à 25-40 sources selon le type |
| Investisseurs | type dédié adossé à la base propriétaire (fonds groupés par société de gestion, réseaux BA), élargissement taxonomique si secteur vide |
| Modèle | toujours tier `report` (Claude Sonnet, 32 000 tokens), reprise automatique sur troncature jusqu'à 3 fois ; si encore tronqué → dégradé, non facturé |
| Streaming | événements SSE de progression (5 → 20 → 40 %, battement toutes les 8 s jusqu'à 85 %), génération et archivage dans un thread avec sa propre session : **survit à la fermeture du navigateur** (testé) |
| Archivage | `reports` (contenu markdown, sources JSON, viz JSON, tokens, coût modèle, coût recherche, appels, durée) |
| Après | viz compilées et mises en cache par empreinte, email de notification, PDF ReportLab à la demande (filigrane, polices Liberation) |

### Données de production
| Mesure | Valeur |
|---|---|
| Rapports en base | 46 (24 études de marché, 9 concurrentielles, 6 synthèses, 4 risques, 2 réglementaires, 1 investisseurs) |
| Sur 45 jours | 19 rapports, 34 600 caractères en moyenne |
| Coût moyen par rapport | 0,58 € de modèle + 0,08 € de recherche (15 appels) |
| Rapport test du 11/09 | 4 min 04, 29 sources, 21 sections, 2 tableaux, 5 graphiques, 29 900 caractères |
| Premier rapport offert (compte QA) | 7 min 22, 51 400 caractères, 0,65 € — annoncé « ~30 s » dans l'onboarding |

### Observé pendant le rapport test
- La pastille de crédits n'a pas bougé (34 affiché, 9 en base) après le
  débit de 25 crédits : même défaut que celui corrigé pour les conversations.
- Le chrono s'est figé à 1:11 alors que le pourcentage continuait (85 % à
  2 min 54) : le pourcentage est une estimation, pas une mesure.
- La synthèse exécutive dit honnêtement qu'aucune source ne documente la
  catégorie demandée et cartographie quatre catégories voisines : le modèle
  respecte ses sources, mais l'utilisateur a payé 25 crédits pour apprendre
  que son marché « n'apparaît dans aucun classement ».

---

## 2. Ce que l'utilisateur ne peut pas faire
- Supprimer un rapport (le backend le permet, le front ne le propose pas),
  le renommer, l'archiver, le classer, le retrouver par recherche.
- Arrêter une génération, modifier sa question après lancement, régénérer
  une section ou le rapport.
- Revenir sur une génération après un rechargement de page : l'écran
  « Génération en cours » disparaît, le rapport n'apparaît que dans la liste
  quand il est fini, sans signal.
- Voir ce qu'a coûté un rapport (tokens et coûts sont en base, jamais
  exposés), ni savoir qu'un rapport est « dégradé » (le champ existe, le
  front ne le lit pas).
- Donner un avis dans l'app (Google Form externe, aucune donnée reliée au
  rapport).
- Partager par lien, comparer deux rapports, exporter autrement qu'en PDF
  ou vers Notion.
- Choisir une profondeur (les clés i18n Scan / Standard / Approfondi
  existent, aucun composant ne les utilise).

---

## 3. Irritants classés

### A. Bloquants pour la valeur
1. **Attente aveugle de 4 à 7 minutes.** Pourcentage estimé, chrono qui se
   fige, pas de vraie étape (« 12 sources trouvées », « rédaction : section
   3/8 »), pas de reprise si on recharge la page, pas d'annulation.
2. **Un rapport payé peut ne rien apprendre.** Quand les sources ne couvrent
   pas le sujet, le rapport le dit, mais après débit. Aucun aperçu des
   sources avant de lancer, aucune option « moins cher / plus court ».
3. **Solde non rafraîchi** après débit, et deux écrans différents pour la
   même cause (« crédits insuffisants » avant l'envoi = `ReportsQuota`,
   pendant = modale + carte).
4. **Rapport dégradé indiscernable** d'un rapport complet.

### B. Frictions quotidiennes
5. Liste « Vos rapports » sans suppression, renommage, type affiché, tri,
   recherche ni pagination.
6. Ouvrir un rapport archivé en échec ne montre rien (`catch` vide).
7. Retour utilisateur hors de l'app : aucune donnée exploitable.
8. Promesse d'onboarding « ~30 s » contre 7 minutes réelles.
9. Aucune règle d'impression, aucune garantie de parité écran / PDF.

### C. Dette invisible mais coûteuse
10. **Débit et archivage non atomiques** : deux commits distincts ; un échec
    d'archivage après débit = crédits perdus sans rapport ni remboursement.
11. `POST /reports` crée un rapport arbitraire sans passer par le pipeline
    (aucune validation, aucun coût).
12. Images de graphiques servies sans authentification, cache d'un an, sur
    la seule imprévisibilité de l'empreinte.
13. Premier rapport offert protégé par une lecture applicative, pas par une
    contrainte d'unicité : deux appels simultanés = deux rapports gratuits.
14. Import des rapports hérités relancé à **chaque** connexion (et à chaque
    réinitialisation de mot de passe), sans cache ni condition d'arrêt.
15. Coût de recherche mesuré mais jamais exposé ; tarifs des fournisseurs
    « à confirmer » dans le code.
16. Alias legacy dupliqués (`prompts._ALIASES` vs `catalog._ALIASES`),
    `ANALYSIS_PROMPTS` mort, cache investisseurs en mémoire de process.
17. Chemin bloquant `/analysis/run` sans le mécanisme de survie ni test,
    contrairement à `/stream`.
18. CSS d'un éditeur à trois colonnes qui n'existe plus (rail, outline,
    confiance par section, cartes de suggestion) ; clés i18n de profondeur
    et de « donnée insuffisante » jamais utilisées.

---

## 4. Pistes — améliorer, simplifier, supprimer

### Améliorer
| # | Piste | Effet | Effort |
|---|---|---|---|
| 1 | **Génération suivie par identifiant** : ligne `reports` créée dès le lancement avec `statut` (`en_cours`, `termine`, `echec`, `degrade`) et `etape`, progression écrite par le thread, front qui reprend par `GET /reports/{id}` après rechargement ; vraies étapes (sources trouvées, section en cours) | attente lisible, résiliente | moyen |
| 2 | **Aperçu avant débit** : recherche seule (quelques secondes) → « 18 sources trouvées, dont 4 sur votre marché » → l'utilisateur confirme ou reformule ; si trop peu de sources, proposer une synthèse courte moins chère | plus de rapport payé pour rien | moyen |
| 3 | Stop pendant la génération (annulation côté thread, non facturé) | contrôle | faible |
| 4 | Solde rafraîchi depuis le payload final, un seul écran « crédits insuffisants » (modale partagée avec les conversations) | cohérence | très faible |
| 5 | Bandeau « rapport partiel / dégradé » avec la raison, à partir des champs déjà envoyés | honnêteté | très faible |
| 6 | Liste : supprimer (route existante), renommer, type et coût affichés, tri, recherche, pagination | hygiène | faible |
| 7 | Coût par rapport (crédits · tokens, € admin) dans l'en-tête, comme pour les conversations | transparence | faible |
| 8 | Avis dans l'app : note 1-5 + commentaire stockés avec l'id du rapport (table `report_feedback`), remplace le Google Form | donnée exploitable | faible |
| 9 | Onboarding : remplacer « ~30 s » par « quelques minutes, vous recevrez un email » | promesse tenue | très faible |

### Simplifier
| # | Piste |
|---|---|
| 10 | Débit et archivage dans une seule transaction (même correctif que les conversations) |
| 11 | Une seule table d'alias, `ANALYSIS_PROMPTS` supprimé, `POST /reports` réservé aux imports (ou supprimé) |
| 12 | Import hérité déclenché une fois (drapeau `legacy_verifie` sur le compte), plus à chaque connexion |
| 13 | Contrainte unique `(user_id, action)` sur `credit_events` pour le rapport offert |
| 14 | Images viz : URL signée liée au rapport ou authentification, cache court |
| 15 | CSS mort et clés i18n orphelines retirés (éditeur trois colonnes, profondeur, lacunes) |

### Supprimer ou trancher
| # | Élément | Question |
|---|---|---|
| 16 | « Étude personnalisée » (40 crédits) | La tuile envoie en réalité `synthese_executive` (App.jsx:34) : c'est une synthèse exécutive facturée 40 au lieu de 25, sans directive libre. Soit une vraie directive personnalisée, soit retirer la tuile, soit aligner le prix. |
| 17 | Sélecteur de profondeur (préparé, jamais branché) | Le construire (Scan 10 crédits / Standard / Approfondi) ou effacer ses traces. |
| 18 | Chemin bloquant `/analysis/run` | Garder seulement comme repli si le SSE n'ouvre pas, avec le même mécanisme de survie, ou le retirer. |
| 19 | Livraison Notion vs Google Drive | Drive commenté partout : le brancher ou l'enlever. |

---

## 5. Ordre proposé
1. Quick wins : solde rafraîchi, écran crédits unique, bandeau dégradé,
   promesse d'onboarding, suppression/renommage/coût dans la liste (#4-#9).
2. Transaction unique débit + archivage, contrainte unique du rapport
   offert, import hérité une fois (#10, #12, #13).
3. Génération suivie par identifiant avec vraies étapes, reprise après
   rechargement, Stop (#1, #3).
4. Aperçu des sources avant débit (#2) — décision produit.
5. Décisions #16-#19, puis nettoyage (#11, #14, #15).
