# Déroulé du workshop Axial — 16/09, 9 h à 13 h

Objectif : chaque participant repart avec un compte actif, un rapport produit
sur sa propre entreprise et une conversation sourcée, et comprend ce qu'Axial
fait de différent (sources vérifiées, base investisseurs, registre des
entreprises, mémoire d'entreprise).

## Avant 9 h (5 minutes)

- Vérifier les services : `ssh hostinger "systemctl is-active axial-backend axial-worker axial-frontend"` → trois `active`.
- Ouvrir `https://app.axial-ia.fr` sur l'écran de présentation, connecté avec
  ton compte admin : Pilotage montre la santé des fournisseurs (bouton de
  contrôle réel) et le compteur de comptes.
- Écrire au tableau l'adresse `app.axial-ia.fr` et deux consignes : créer le
  compte avec l'email professionnel, choisir « Continuer sans carte ».

## Séquence 1 — Inscription et contexte (9 h 00 – 9 h 30)

1. Les participants créent leur compte, en décalé de quelques minutes si le
   groupe est grand (chaque inscription lance en arrière-plan un rapport
   offert de 5 à 9 minutes ; dix en même temps ralentissent tout le monde).
2. Étape 1 : nom de l'entreprise, site web (le bouton « Pré-remplir depuis mon
   site » lit la page d'accueil), secteur, stade, défi, marché, une phrase de
   positionnement. Insister : c'est cette mémoire qui personnalise tout.
3. Étape 2 : aperçu, un clic.
4. Étape 3 : « Continuer sans carte » (100 crédits offerts, aucune carte).
5. Étape 4 : « Lancer cette analyse » — le premier rapport offert part, l'email
   arrivera quand il sera prêt. Pendant ce temps, on passe aux conversations.
   Pièges à annoncer : mot de passe de 8 caractères minimum ; un rechargement
   de page garde le contexte ; une déconnexion puis reconnexion repasse par
   l'écran carte, où « Continuer sans carte » est disponible.

## Séquence 2 — Conversations (9 h 30 – 10 h 15)

Montrer sur l'écran, puis laisser faire :
- Une question de levée de fonds (« Comment préparer notre seed : quels fonds
  cibler ? ») : les premières sources sont des fonds et réseaux de la base
  investisseurs Axial, triés sur le secteur et le stade du profil.
- Une question réglementaire (« Quelles obligations RGPD et AI Act pour mon
  produit ? ») : sources officielles récentes (CNIL, EUR-Lex, guides AMF et
  Bpifrance présents dans la base de connaissance, rendus « Document de
  référence »).
- Une question de marché avec des concurrents nommés : le message de suivi
  garde le fil (mémoire de conversation), le coût s'affiche sous chaque réponse
  (2 crédits).
- Montrer le menu ⋯ : renommer, épingler, dossiers, régénérer, Stop.

## Séquence 3 — Rapports (10 h 15 – 11 h 30)

- Chaque participant lance UN rapport sur sa propre question. Recommander la
  cartographie concurrentielle (25 crédits, 4 à 6 minutes) avec ses concurrents
  nommés dans la question : les fiches du registre des entreprises (Pappers)
  apparaissent dans les sources avec SIREN, effectifs et comptes.
- Pendant la génération : étapes réelles (recherche, sélection, couverture,
  rédaction section par section), Stop possible, on peut naviguer ailleurs.
- À la fin : synthèse exécutive, tableaux et graphiques, citations cliquables,
  bandeau « Couverture partielle » s'il y a lieu (à expliquer : Axial dit quand
  les sources ne suffisent pas plutôt que d'inventer), export PDF, partage par
  lien public, « Signaler un problème ».
- Le rapport offert de l'inscription est arrivé entre-temps : l'ouvrir depuis
  « Vos rapports » ou l'email.
- Budget : 100 crédits = par exemple 1 étude de marché (40) + 1 cartographie
  (25) + 15 messages. Recharge possible depuis Pilotage pendant la séance.

## Séquence 4 — Mémoire, agents, questions (11 h 30 – 12 h 30)

- Mémoire : importer un document (deck, business plan) et reposer une question
  qui l'utilise ; Notion connectable.
- Agents de veille : créer une veille sur un concurrent ou un sujet
  réglementaire, montrer un résultat existant sur ton compte (les premiers
  résultats des nouveaux agents arrivent après la séance).
- Cartographie investisseurs (30 crédits) sur un volontaire : la liste vient
  de la base propriétaire, pas du web.
- Tour de table : retours produit, ce qui manque, ce qu'ils paieraient.

## Conclusion (12 h 30 – 13 h)

- Plans et crédits (Crédits > offres), essai 14 jours, comment recharger.
- Rappeler l'email de fin de rapport et le lien de partage public.
- Recueillir les emails des intéressés pour la relance du jeudi.

## Si quelque chose casse

| Symptôme | Réflexe |
|---|---|
| Page blanche ou erreur sur tous les postes | `ssh hostinger "sudo systemctl restart axial-backend axial-worker"` puis recharger |
| « Session expirée » pour un participant | se reconnecter ; le rechargement seul suffit souvent |
| Rapport figé plus de 15 minutes | Stop, puis « Régénérer » ; le débit n'a lieu qu'à la fin |
| « Sources insuffisantes » | reformuler la question avec des noms ou un marché plus précis, ou « Recherche élargie » |
| Un participant sans crédits | Pilotage > comptes > créditer |
| Bandeau « nouvelle version » | ne doit pas apparaître : rien n'est déployé ce matin |

Tout incident fournisseur t'arrive par email (dédupliqué à l'heure) ; les
services redémarrent seuls après un plantage.
