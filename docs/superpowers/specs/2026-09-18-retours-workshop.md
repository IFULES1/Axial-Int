# Retours du workshop VC Ready du 16/09 — classement, écarts, améliorations

Source : page Notion « 16/09 - Retours workshops - ciblage investisseurs »
(Miradie, 17/09). Chaque retour est confronté à ce que la base de prod et le
code montrent au 18/09.

## A. Bugs et incohérences signalés

| # | Retour | Ce que montrent la base et le code | Écart | Amélioration | Effort |
|---|---|---|---|---|---|
| A1 | « 10 investisseurs demandés, 5 proposés » | Le moteur remet au modèle 15 fonds + 15 réseaux max (`map_for_profile(limit=15)`) ; sur les 11 cartographies du 16/09, 8 rapports avaient 16 investisseurs de la base dans leurs sources, 2 en avaient 10, 1 en avait 3. C'est le **modèle de rédaction** qui n'en retient que 5 : la directive ne lui impose pas le nombre demandé. | Le nombre demandé dans la question n'est pas un paramètre du rapport. | Lire « N investisseurs » dans la question (`5 à 10` → 10) et l'imposer dans la directive (« présente exactement N acteurs, par ordre de priorité ») ; si la base en fournit moins, le dire. Touche aux prompts : à valider par Miradie. | faible |
| A2 | « 300 K€ interprété comme 3 M€ » | La question réelle en base : « Je prépare une levée de **300 000k€** » (BIBO). Écrit tel quel, c'est 300 M€ ; le modèle a lu 3 M€. Le même rapport avait un pitch de 7 024 caractères collé en question, ce qui a fait échouer Tavily (corrigé le 18/09 : requête bornée à 400 caractères). | Pas de normalisation des montants avant la recherche et la rédaction. | Extraire montant et stade de la question (regex + confirmation), les afficher en tête de l'écran de génération (« Levée : 300 000 € · pré-seed », modifiable) et les passer au moteur en champs structurés. | moyen |
| A3 | « Xavier Niel proposé pour 500 K€ » | Les noms hors base viennent des **sources web** du rapport (les cartographies du 16/09 avaient 4 à 10 sources web à côté des 10 à 16 de la base). Le modèle mélange les deux sans marquer l'origine. | Le rapport ne distingue pas « base Axial, filtrée sur ton stade » et « cité par la presse ». | Deux sections imposées : « Investisseurs de la base Axial (secteur + stade) » puis « Autres noms cités dans les sources web, à vérifier » ; ou couper le web pour ce type (le champ `sources` par type existe depuis Sources v2 : `web: False` pour `cartographie_investisseurs`, avec la fraîcheur en option). | faible |
| A4 | Flux RSS ajouté « n'apparaît pas » | Le flux est **enregistré** : 9 flux créés par Venturix le 16/09 (Ouest-France Le Marin en URL libre à 10 h 13, puis 8 du catalogue), tous actifs, tous renvoyés par `GET /watches/feeds` et rendus dans « Mes flux » (titre ou URL). | Ce que l'utilisateur regarde ensuite, c'est **son agent** : un agent n'exploite que les flux dont la catégorie correspond à sa compétence (`_feeds_for(skill.rss_categories)`), et sa fiche ne liste pas les flux qu'il utilise. Un flux « startup » ajouté pour un agent « concurrentiel » est invisible et inutilisé. | Afficher sur la fiche de l'agent les flux qu'il lit ; laisser l'utilisateur rattacher un flux à un agent (case à cocher) au lieu d'une catégorie devinée ; récupérer le titre du flux à l'ajout. | moyen |

## B. Pertinence du ciblage selon le stade

| Retour | État actuel | Écart | Amélioration | Effort |
|---|---|---|---|---|
| Des VC proposés à des pre-seed ; bien meilleur quand le fondateur écrit « Business Angels en priorité » ou nomme des investisseurs déjà contactés | La base classe fonds et réseaux séparément ; le score dépend du secteur et du stade (`_score`), l'élargissement remonte des stades voisins quand le secteur est vide. Les réseaux de BA sont remis au modèle après les fonds, jamais en tête. Rien ne lit « déjà contactés ». | Le stade influence le tri, pas la **composition** de la réponse : pre-seed reçoit la même structure fonds-d'abord que série A. | Règle par stade : idéation / pre-seed → réseaux de BA, dispositifs non dilutifs (Bpifrance, régions, concours : à ajouter en base ou en base de connaissance), family offices ; seed → BA + fonds d'amorçage ; série A+ → fonds. Exclure les noms « déjà contactés » (champ dans la question ou dans le profil). Prompt à valider par Miradie. | moyen |

## C. Base investisseurs

| Retour | État actuel | Écart | Amélioration | Effort |
|---|---|---|---|---|
| Peu de Business Angels | 111 réseaux de BA, 0 BA individuel (chantier « BA individuels » ouvert depuis août : pistes = communiqués de levées). 466 sociétés de gestion, 1 489 fonds. | Les pre-seed du batch cherchent des BA nommés, pas des réseaux. | Rouvrir le chantier BA individuels : extraction depuis les communiqués de levées (noms cités), annuaires publics (France Angels, Business Angels des Grandes Écoles), avec secteur / ticket / région ; afficher la source. | élevé |
| Dates de création des véhicules, dates de levées, dry powder | Le moteur ne charge que quelques colonnes (identifiants, nom, site) ; les dates de millésime et de closing ne sont ni chargées ni, pour la plupart, en base. | Aucune notion de **timing** : un fonds en fin de période d'investissement est proposé comme un fonds fraîchement levé. | Ajouter en base « millésime du dernier véhicule », « date du dernier closing », « taille » (sources : France Invest, communiqués, AMF) ; en déduire un indicateur « capacité probable » (levé depuis < 3 ans = actif) et l'afficher dans le rapport. | élevé |

## D. Signaux positifs à conserver

- Effet « wow » du premier rapport, découverte d'investisseurs inconnus, confirmation du ciblage existant.
- **Deux tiers des participants ont demandé plus de crédits** : la dotation passée à 100 le 15/09 a servi ; 12 comptes ont consommé de 8 à 80 crédits (soldes de 20 à 92).
- Une utilisatrice de GPTs a jugé les investisseurs « très pertinents » et non trouvés par ChatGPT : l'argument « base propriétaire » est validé.
- Un compte revenu le lendemain (OHé, 14 messages) : premier signe d'usage récurrent depuis le lancement.

## E. Profils et besoins clients (positionnement)

| Profil | Besoin exprimé | Ce qu'Axial fait déjà | Manque | Piste |
|---|---|---|---|---|
| Fondateur peu familier des outils IA, en levée, sans temps : « vous le faites pour moi et je paie » | Veille et prospection déléguées, CRM investisseurs à jour, événements de pitch, demo days, opportunités de financement, actualités de sa levée | Rapports, agents de veille (RSS + web), mémoire d'entreprise | Pas de CRM investisseurs, pas de calendrier d'événements, pas de suivi de relation, pas d'offre « service » | Offre accompagnée : un agent « levée » qui tient la liste des cibles, leur statut et les relances, plus une veille événements (sources : Station F, French Tech, Bpifrance, incubateurs) ; facturation au service. |
| Fondatrice équipée de GPTs | Découverte au-delà de ChatGPT | Base propriétaire | — | Mettre en avant « non trouvés ailleurs » dans le rapport (déjà vrai, à dire). |

## F. Le pain majeur : accéder aux investisseurs

Retour le plus fort : « qui cibler » ne suffit pas ; il faut « comment l'atteindre et par qui passer ». Cold emails inefficaces, warm intro sous-utilisée, épuisement du networking (10 cafés par semaine).

État actuel : Axial s'arrête à « identifier ». Aucune donnée de partenaires en base n'est exposée (782 partners importés en août, sans email ni LinkedIn), aucun graphe de relations, aucun suivi.

Améliorations, par ordre de faisabilité :
1. **Le bon interlocuteur** : exposer dans le rapport le partner responsable du secteur (données partners déjà en base) et son profil LinkedIn public, avec un angle d'approche.
2. **Chemin d'intro** : croiser les fonds cibles avec le portefeuille (startups déjà financées, sur le site du fonds) et proposer « une startup de leur portefeuille dans votre secteur à qui demander une intro ».
3. **Suivi** : un tableau « ma levée » dans l'app (cible, statut, prochaine action, date) alimenté par le rapport, exportable ; c'est le CRM demandé par le profil E.
4. **Tables rondes sectorielles investisseurs × startups** (idée de Chloé) : hors produit, mais Axial peut fournir la liste des fonds actifs du secteur et les dossiers des startups participantes.

## G. Insight stratégique

Chaîne de valeur cible : identifier → prioriser → comprendre → trouver le bon interlocuteur → créer une warm intro → suivre la relation. Pour les plus early-stage : BA + non dilutif + réseau qualifié + événements + introductions, et cesser de laisser entendre que « levée = VC ».

Ce que le produit couvre aujourd'hui : les deux premiers maillons, avec un biais VC. Les maillons 3 à 6 sont vides et sont ceux que les participants ont réclamés.

## H. Priorisation proposée

| Priorité | Sujet | Pourquoi d'abord |
|---|---|---|
| 1 | A1 + A3 + B : nombre demandé respecté, base séparée du web, composition par stade | Trois corrections de directive et d'ordre de sources, visibles dès le prochain rapport, sans nouvelle donnée. Prompts à valider par Miradie. |
| 2 | A2 : montant et stade extraits et confirmés | Évite les contresens coûteux (40 crédits pour un rapport sur le mauvais montant). |
| 3 | A4 : flux rattachés aux agents et visibles | Petit, et un participant a buté dessus. |
| 4 | F1 + F3 : bon interlocuteur, tableau de suivi de levée | Le pain majeur, avec des données déjà en base pour F1. |
| 5 | C : BA individuels, dates et capacité des fonds | Le plus long : collecte de données. |
| 6 | E : offre accompagnée, veille événements | Positionnement, à décider avant de construire. |

Correctifs déjà faits depuis le workshop : requête Tavily bornée à 400 caractères (18/09).
