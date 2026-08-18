# Backlog Axial — chantiers notés par Miradie

> Fichier de collecte : les chantiers y sont notés au fil de l'eau pour ne rien oublier,
> sans les mélanger avec les travaux en cours. Retirer les entrées une fois livrées.

## Noté le 18/08/2026

### Parcours & données
- [ ] **Purger toutes les données mockées** de l'app — l'utilisateur doit faire son parcours de A à Z avec ses vraies informations uniquement.
- [ ] **Onboarding ↔ Mémoire alignés** : demander à l'onboarding exactement les mêmes informations que celles de l'onglet Mémoire (constat : les infos saisies à l'onboarding ne se retrouvent pas ensuite dans la mémoire) + **chargement de documents dès l'onboarding**.
- [ ] **Inverser les étapes 3 et 4** de l'onboarding (carte avant la première question).
- [ ] **Ne pas lancer d'analyse automatiquement** après l'onboarding.

### Crédits & facturation
- [ ] Onglet **Crédits** : afficher le **plan actuel** de l'utilisateur + la **date du prochain prélèvement**.
- [ ] **Paramètres** : historique de **consommation de crédits** + historique de **facturation relié à Stripe** (récupération directe des factures).

### Navigation & UI
- [ ] Vérifier que **tous les boutons retour** mènent au bon endroit.
- [ ] **Réagencer la page Documentation** pour la rendre lisible.

### Notifications & paramètres
- [ ] **Notifications par email** à mettre en place ; **supprimer** les types « mentions » et « commentaires ».
- [ ] Paramètres > Espace de travail : **retirer « Membres »** pour le moment (reviendra avec la mise en place des sièges).

## Déjà en file (sessions précédentes)
- [ ] Refresh token frontend (401 silencieux après ~1h) — gardé pour la fin sur décision du 17/08.
- [ ] Cleanage front : estimations rapports fictives (`estCredits`), typo « marcé », dark mode Rapports, wordings agents/documents.
- [ ] Blocage serveur de l'étape carte (tracker l'état d'abonnement en base).
- [ ] Robustesse + légal : durcissement VPS, RGPD/CGU, monitoring.
- [ ] Data/veille : tag Inoreader « concurrents [secteur] », filtrage bruit RSS.
