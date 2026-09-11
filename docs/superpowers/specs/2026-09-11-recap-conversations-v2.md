# Conversations v2 — récapitulatif de livraison (11/09/2026)

Branche `conversations-v2` fusionnée dans `main` et déployée en production le
11/09 (commits `38c483b..d37587a`, 22 commits). Spec :
`2026-09-10-conversations-v2.md` ; plan : `docs/superpowers/plans/2026-09-10-conversations-v2.md`.

## 1. Ce qui change pour l'utilisateur

| Domaine | Avant | Après |
|---|---|---|
| Mémoire de fil | chaque message partait seul au modèle | 8 derniers tours envoyés (1 500 car. chacun), résumé roulant incrémental au-delà, généré en tâche de fond |
| Question de suite | recherche web sur la question brute (« Développe le point 2 » → sources hors sujet) | la requête accole le sujet du fil (titre) |
| Attente | bandeau unique « AXIAL analyse… » | « Recherche web… » → « N sources lues » → « Rédaction… » avec chrono |
| Affichage | la réponse se réécrivait après le flux | le texte ne se réinitialise jamais ; auto-défilement si l'on est en bas, bouton ↓ sinon |
| Contrôle | rien | Stop (réponse archivée « partielle », non facturée), composer verrouillé par fil, note « Agent changé » |
| Crédits | solde jamais rafraîchi, refus opaque | solde mis à jour à chaque réponse ; modale « Plus de crédits » avant l'envoi et sur 402 ; coût sous chaque réponse (crédits · tokens) et total du fil |
| Contexte | silencieux | bandeau « profil entreprise vide » avec lien ; limite de 3 documents ; erreurs d'import nommées ; « Réindexer » si un document n'a pas de texte |
| Gestion | aucune | dossiers (défaut « Général »), épingler, archiver, renommer inline, déplacer, supprimer avec confirmation, recherche dans le contenu avec extraits |
| Réponses | copier seulement | Régénérer (dernière réponse), Éditer un message envoyé (relance à partir de là), pagination « Charger les messages précédents » |
| Markdown | listes numérotées, liens, code en texte brut | parseur complet testé (29 tests Node) |
| Erreurs | « ⚠️ e.message » | cartes nommées : crédits, session expirée (retour à la connexion), réseau + Réessayer (même clé d'idempotence), message trop long |
| Mobile | colonne des conversations à 280 px fixes | tiroir des conversations, composer collé en bas, toutes les surfaces sans débordement à 375 px |

## 2. Ce qui change côté plateforme

- Routage réel en mode « Conversation » (`DEFAULT_AGENT = auto`, `personas.route`
  appelé) ; `/intelligence/agents` authentifié ; `/agents/route` supprimé.
- Migration `0022_conversations_v2` : `messages.statut / cle_idempotence /
  cout_recherche_micro_eur / appels_recherche`, `conversations.resume /
  resume_messages / pinned_at / archived_at`, index unique composite
  `(conversation_id, cle_idempotence)` créé en `CONCURRENTLY`.
- Coût de recherche mesuré par message (3 appels ≈ 0,017 € observé) et lu par
  le tableau de bord admin.
- Facturation : 2 crédits uniquement sur une réponse `complet`, débit et
  message dans la même transaction ; idempotence par en-tête
  `X-Idempotency-Key` ; reprise automatique sur troncature en flux (2 fois).
- Déconnexion client : générateur async côté routeur, archivage du partiel dans
  une session dédiée.
- Notification email sur toute erreur backend non gérée et sur les échecs de
  génération : `miradie.buranturu@axial-ia.fr`, dédupliquée par heure, secrets
  masqués, envoi en fil démon, désactivable par `ERREURS_NOTIF_ACTIVES=false`.
- Dette retirée : `axChat`, `axNewConversation`, `_convId`, `ensureConversation`,
  `SUGGESTED_PROMPTS` en dur, `common.share`, `share.title`, `_TITRES_PAR_DEFAUT`,
  parsing SSE dupliqué ; cache Notion borné (TTL 10 min, 200 entrées).
- Tests : 271 backend (SQLite mémoire, LLM simulé, flux de bout en bout,
  déconnexion, idempotence, facturation, 401, routage réel), 29 Node
  (markdown, garde des imports du bridge).

## 3. Parcours réel en production (11/09, compte `qa-cv2-1109@axial-qa.fr`)

| Étape | Résultat |
|---|---|
| Inscription neuve, onboarding, écran carte | OK |
| Question 1 (libre) | réponse complète, 2 graphiques, sources, solde 40 → 38 |
| Question 2 « Développe le point 2… » | mémoire OK (« ma réponse précédente ») ; sources hors sujet → **correctif déployé** (requête = titre + question) |
| Question 3 + Stop après 18 s | bulle « Réponse partielle », solde inchangé (36), archivée `partiel` en base, composer libéré ; « Régénérer » absent avant rechargement → **correctif déployé** |
| Régénérer | nouvelle réponse complète, solde 36 → 34, total du fil « 4 crédits · 15 k tokens » |
| Épingler, renommer, dossier « Tests », déplacer, recherche « indicateurs » (2 extraits surlignés), archiver, supprimer avec confirmation | OK |
| Mobile 375 px sur la prod | sans débordement, tiroir des conversations |
| Email de notification d'erreur | non provoqué (aucune 500 réelle pendant le parcours) — à observer sur la première erreur réelle |

Base après parcours : 6 messages (statuts `complet` ×5, `partiel` ×1), solde
34, coût de recherche 16 600 µ€ par message, résumé non encore déclenché
(6 messages < 8).

## 4. Points restants (mineurs, à traiter dans une prochaine vague)

1. Une réponse arrêtée avant le premier mot affiche un badge « Réponse
   partielle » sur une bulle vide : préférer « Réponse interrompue » avec le
   bouton Régénérer en évidence.
2. Le compteur d'un dossier n'inclut pas ses conversations épinglées (elles
   sont affichées dans « Épinglées »).
3. « ARCHIVÉES » apparaît une fois par dossier et une fois globalement.
4. L'écran carte réapparaît à chaque rechargement pour un compte sans carte
   (comportement antérieur, hors périmètre).
5. Migration : si l'index concurrent échoue, le créer à la main puis
   `alembic stamp head` (l'`autocommit_block` a déjà validé les colonnes).
6. Garde des imports limitée aux identifiants `ax*` (F12, écarté).
7. Wording global des prompts et descriptions : toujours en attente de Miradie.

## 5. Arbitrages pris pendant l'exécution

- « Axial route seul » = sélecteur conservé, défaut `auto`, routeur réel,
  badge de l'agent qui a répondu.
- Les projets deviennent des dossiers visibles ; dossier par défaut « Général ».
- Pièces jointes non rejouées à la régénération / édition (non stockées sur
  le message).
- Plus de conversation locale de repli quand la création échoue : carte
  d'erreur + Réessayer qui recrée.
- Documents en attente conservés après Stop.
- Statut `partiel` jamais facturé ; clé d'idempotence posée seulement sur
  `complet`.
- Résumé roulant en fil démon avec sa propre session, un seul par conversation.
- Le message trivial (< 25 caractères) déclenche la recherche s'il est routé
  vers un spécialiste.
