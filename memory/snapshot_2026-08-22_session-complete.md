# Snapshot — 22/08/2026 — Session complète (à lire en priorité à la reprise)

## Où on en est en une phrase
Les 5 chantiers du 20/08 sont **livrés**. L'app est en production, la campagne de
migration est partie, et le vrai problème n'est plus technique : **personne ne
traverse l'onboarding**.

## Chantiers — état final
| # | Chantier | État |
|---|---|---|
| ⑤ | Vérification des rapports vs ancienne app | ✅ lot A livré · ⏸ **reste le retour de Miradie sur le FOND** |
| ① | Streaming | ✅ rapports (SSE + battements de cœur) et chat (mot à mot) |
| ③ | Connexion DB-investisseur | ✅ 6e type de rapport, scoring porté à l'identique |
| ② | Migration des utilisateurs | ✅ 42 emails, restauration auto, bonus 30 crédits |
| ④ | Connexions outils client | ✅ Notion (API REST) · Drive masqué · Gmail bloqué par Google |
| + | Internationalisation | ✅ miroir linguistique |

## Décisions structurantes prises ce jour
- **Miroir linguistique** : la langue de la QUESTION commande la langue de la réponse (pas un réglage de profil). La préférence de profil ne sert qu'aux emails automatiques, qui n'ont pas de question à refléter.
- **Notion : abandon du connecteur MCP** — `mcp.notion.com` exige son propre OAuth, incompatible avec le jeton d'intégration. Passage à l'API REST : le corpus de l'espace partagé (12 pages, cache 15 min) rejoint le pool de sources et c'est le reranker qui arbitre.
- **Google Drive masqué** dans l'interface (backend prêt) ; **Gmail hors de portée** (portée restreinte, validation + audit annuel payant).
- **Renouvellements bloqués** chez Stripe (`cancel_at_period_end`) : `admin@axial.com` (01/09) et `christian@eqonx.com` (05/09). Accès conservé jusqu'à ces dates, aucun prélèvement. Réversible en une commande.
- **Le registre FR n'est PAS une dette** : les emails viennent de Miradie (tutoiement), l'app est impersonnelle (vouvoiement). Décision assumée.
- **Andy, Isaia (×2)** en liste d'exclusion email permanente.

## Le constat qui compte
**Tunnel d'activation : 43 contactés → 2 comptes → 0 usage.**
- `soumeya@optimpharma.fr` : inscrite, 22 rapports restaurés, **profil jamais rempli** — n'a jamais vu l'app.
- `christian@eqonx.com` : a franchi TOUT l'onboarding, carte comprise, **et n'a posé aucune question**.

Deux personnes, deux abandons, à deux endroits différents du même parcours. Le
sujet le plus rentable n'est plus d'amener du monde mais de **leur faire franchir
la porte**.

**Emails** : 43 envois, 34 ouvertures dont 18 pré-chargements automatiques et
**17 ouvertures répétées** (les seules lectures humaines certaines). Christian a
ouvert 12 fois, Soumeya 10 — les deux qui se sont inscrits. **15 lecteurs tièdes**
ont relu sans s'inscrire : Sarah Gebai (6), Ahmed Mamdouh (4), Franz Vasseur (4),
s.gorjux (3), calebmeinerad (3)… → relance prévue le **25/08**.

## Outil créé
`/audit-activation-axial` — skill qui rejoue tout ça en une commande (tunnel,
individus bloqués, comptes actifs, ouvertures d'emails, points d'attention).
Deux pièges qu'il évite : les rapports restaurés ne comptent pas comme un usage,
et un tunnel non monotone est signalé comme anomalie.

## Ce qui reste
1. **Séquences email automatiques** — chantier suivant, décidé avec Miradie. Commencer par J-3 fin d'essai.
2. **L'onboarding qui perd tout le monde** — le plus rentable structurellement.
3. Miradie : relances du 25/08, retour sur le fond des rapports, mentions légales (SIREN), régénération de la clé `service_role` de DB-investisseur, tag Inoreader.
4. Dettes : garde PII désactivé (`PII_GUARD_MODE=off`), 6e type d'analyse `analyse_reglementaire` manquant, 4 comptes de test en prod, 12 secteurs sans investisseur tagué.

## Incidents du jour (à ne pas reproduire)
- **Migration 0016 non appliquée malgré son message de succès** → colonne absente, toute lecture de profil en erreur, production cassée quelques minutes. **Toujours vérifier `alembic current` ET la présence réelle de la colonne après un déploiement avec migration.**
- **Le miroir linguistique ne marchait pas** au premier essai : une consigne d'ancrage rédigée en français imposait une ouverture française. Une instruction de prompt écrite dans une langue impose cette langue — décrire l'intention, pas le gabarit.
- Email de test envoyé par erreur à un vrai utilisateur (`rolland@maydaymayday.net`) : **utiliser une adresse de test**.

## État technique
Prod app.axial-ia.fr · alembic **0016** · 63/63 tests · GitHub `main` = `2dffa64`.
Déploiement : scp → `alembic upgrade head` → **vérifier la version** → restart → rebuild front (`NEXT_PUBLIC_API_URL=https://app.axial-ia.fr/api`).
Secrets posés : Notion (3), investisseurs (2), Resend vérifié.
