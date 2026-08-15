# Snapshot — 2026-08-13 (Wiring backend, lot 2)

## Fait & VÉRIFIÉ à l'écran (UI = prototype exact, données réelles)
En plus d'Auth + Onboarding (lot 1), branchés dans `app/_prototype/App.jsx` via `bridge.js` :
- **Crédits (barre haute)** : fetch `/billing/balance` à l'entrée dans l'app → affiche le vrai solde
  (founder2 = **120**). Remplace le mock "2 481 / 5 000".
- **Identité utilisateur** (sidebar bas) : fetch `/auth/me` → nom/email/initiales réels
  (**FA · founder2@axialtest.com**). Remplace MOCK_USER "Maya Lefebvre".
- **Persistance de session** : au chargement, si token valide → reprise directe dans l'app
  (`route='app'` ou 'onb1' selon onboarding). Token invalide/expiré → purge (`axClearToken`).
- **Logout** : vide le token (`axClearToken`) + retour landing.

### Détail des seams édités (App component)
- import bridge : + `axMe`.
- effet mount : session persistence (axMe → go).
- effet `[route]` : si 'app' → axBalance + axMe → setAxBal / setAxUser.
- topbar chip : `{axBal == null ? '…' : axBal}`.
- `<AppShell user={axUser || MOCK_USER} onLogout={() => { axClearToken(); go('landing'); }} />`.

## Bilan wiring
| Flux | État |
|---|---|
| Auth register/login | ✅ réel (Postgres) |
| Onboarding profil | ✅ réel (company_profiles) |
| Crédits barre haute | ✅ réel (120) |
| Identité user | ✅ réel (founder2) |
| Session persistence + logout | ✅ |
| Workspace/chat (conversations) | ❌ mock (MOCK_CONVERSATIONS) — **nécessite LLM keys** |
| Rapports (/analysis) | ❌ mock — **nécessite LLM keys** |
| Agents (liste/session) | ❌ mock (liste mappable ; session = keys) |
| Mémoire surface | ❌ mock (modèle "faits par catégories" ≠ profil plat backend) |
| Crédits surface (graphe) | ❌ mock (pas d'usage quotidien côté backend) |

## BLOCAGE pour le cœur : clés LLM
Le chat et les rapports = le cœur fonctionnel, mais ils **ne peuvent pas générer** sans
`PERPLEXITY_API_KEY` + `OPENAI_API_KEY` dans `/Users/mirad/axial-intelligence/.env`.
Sans clés : mode dégradé ("recherche web indisponible"). → à fournir pour wirer+tester le chat.

## Notes techniques
- Token JWT local TTL = 3600s (1h). Expiration → 401 → purge auto (géré). Pour dev long, augmenter jwt_ttl_seconds si besoin.
- Mémoire & Crédits-surface : modèles prototype plus riches que le backend → mapping dédié à faire (plus tard).
- Serveurs : backend 127.0.0.1:8090 (uvicorn --reload), front localhost:3005. Docker=8080/3000 (ancien, ne pas toucher).
- Comptes test : founder2@axialtest.com / password123 (onboardé, 120 cr).

## Prochaines étapes
1. **Ajouter les clés LLM** au .env → wirer + tester le chat (workspace) et les rapports (le cœur).
2. Agents : brancher la liste sur /intelligence/agents (sans clé) + session (avec clé).
3. Mémoire & Crédits-surface : mapping dédié prototype↔backend.
4. Puis "autres chantiers" (P7 migration prod, durcissement VPS…).

## Snapshots
…, 18-40 (auth+onboarding), wiring2 (crédits+identité+session+logout).
