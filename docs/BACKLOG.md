# Backlog Axial — chantiers notés par Miradie

> Fichier de collecte : les chantiers y sont notés au fil de l'eau pour ne rien oublier,
> sans les mélanger avec les travaux en cours. Retirer les entrées une fois livrées.

## Noté le 18/08/2026

### Parcours & données
- [x] **Purger toutes les données mockées** *(fait 18/08 : MOCK_USER/MOCK_CONVERSATIONS supprimés, fallback neutre, suggestions personnalisées depuis le vrai profil)*
- [ ] **Onboarding ↔ Mémoire alignés** : demander à l'onboarding exactement les mêmes informations que celles de l'onglet Mémoire (constat : les infos saisies à l'onboarding ne se retrouvent pas ensuite dans la mémoire) + **chargement de documents dès l'onboarding**.
- [x] **Inverser les étapes 3 et 4** *(fait 18/08 : Contexte → Démo → Activation (carte) → Première analyse ; profil sauvegardé dès l'étape 2)*
- [x] **Ne pas lancer d'analyse automatiquement** *(fait 18/08 : la question suggérée pré-remplit le composer, l'utilisateur envoie lui-même)*

### Crédits & facturation
- [x] Onglet **Crédits** : plan actuel + date du prochain prélèvement *(fait 18/08 : carte « Mon abonnement » + bouton Gérer via portail Stripe)*.
- [x] **Paramètres** : historiques conso + factures Stripe *(fait 18/08 : journal `credit_events` + factures avec PDF, onglet Facturation réel)*.

### Navigation & UI
- [ ] Vérifier que **tous les boutons retour** mènent au bon endroit.
- [ ] **Réagencer la page Documentation** pour la rendre lisible.

### Notifications & paramètres
- [ ] **Notifications par email** à mettre en place *(la partie « supprimer mentions/commentaires » est faite le 18/08 ; reste le backend d'envoi réel)*.
- [x] Paramètres > Espace de travail : **retirer « Membres »** *(fait 18/08)*

### Légal (ouvert le 18/08)
- [ ] **Compléter les mentions légales** (`frontend/app/legal/mentions/page.tsx`) : forme juridique, capital, adresse du siège, SIREN/RCS, directeur de la publication — puis faire valider CGU + confidentialité par un juriste.

## Déjà en file (sessions précédentes)
- [ ] Refresh token frontend (401 silencieux après ~1h) — gardé pour la fin sur décision du 17/08.
- [ ] Cleanage front : estimations rapports fictives (`estCredits`), typo « marcé », dark mode Rapports, wordings agents/documents.
- [x] Blocage serveur de l'étape carte *(fait 18/08 : table `user_subscriptions` + gate à la reprise de session basé sur l'état Stripe réel, avec backfill)*.
- [ ] Robustesse + légal : durcissement VPS, RGPD/CGU, monitoring.
- [ ] Data/veille : tag Inoreader « concurrents [secteur] », filtrage bruit RSS.
