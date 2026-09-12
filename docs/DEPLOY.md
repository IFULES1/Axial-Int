# Déploiement Axial sur le VPS (à côté de l'app existante)

Cible : `https://app.axial-ia.fr` — front Next.js + API FastAPI (même domaine, `/api` → backend),
DB + auth **Supabase**, veille worker, Qdrant, emails Resend, paiements Stripe.

Hypothèses : VPS Debian/Ubuntu, tu as un accès sudo, Caddy sert déjà l'ancienne app, `axial-ia.fr` géré chez ton DNS.
Chemin cible : `/opt/axial-intelligence`. Utilisateur système : `axial`.

---

## 0. Prérequis (une fois)
```bash
# utilisateur dédié
sudo useradd -r -m -d /opt/axial-intelligence -s /bin/bash axial

# Doppler CLI (si absent)
curl -Ls https://cli.doppler.com/install.sh | sudo sh

# Node 20 + Python 3.13 + venv (adapte selon ton système), rsync, docker (pour presidio)
```

## 1. DNS
Chez ton registrar : **A record** `app` → IP du VPS. (Propagation : quelques minutes à quelques heures.)

## 2. Code sur le VPS
```bash
sudo -u axial -H bash
cd /opt/axial-intelligence
git clone <ton-repo> .        # ou rsync depuis ton Mac (voir §6 pour la KB)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## 3. Doppler config `prd`
```bash
cd /opt/axial-intelligence
doppler login          # ou doppler configure set token <service-token-prd>
doppler setup --project axial --config prd
```
**Secrets à poser dans la config `prd`** (dashboard Doppler ou `doppler secrets set`, projet axial / config prd) :

| Secret | Valeur |
|---|---|
| `ENVIRONMENT` | `production` |
| `AUTH_MODE` | `supabase` |
| `ALLOWED_ORIGINS` | `https://app.axial-ia.fr` |
| `DATABASE_URL` | (pooler Supabase — je te le donne après création du projet) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET` | (dashboard Supabase → Settings → API) |
| `QDRANT_URL` | `http://localhost:6355` |
| `COHERE_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `EXA_API_KEY`, `TAVILY_API_KEY`, `LINKUP_API_KEY` | (copie de la config dev) |
| `STRIPE_API_KEY` | **clé LIVE** `sk_live_…` (⚠️ NE PAS mettre `STRIPE_TEST_API_KEY` en prd) |
| `STRIPE_WEBHOOK_SECRET` | (webhook live, cf. §8) |
| `RESEND_API_KEY` | (copie de dev) |
| `MAIL_FROM` | `veille@axial-ia.fr` |
| `PII_GUARD_MODE` | `shadow` (ou `enforce`) ; `PRESIDIO_URL=http://localhost:8010` |

> Le schéma DB est appliqué **par moi via l'API Supabase** après création du projet — tu n'as pas à lancer les migrations.

### 3.1 Migration `0023_rapports_v2` — AVANT le redémarrage du backend

Rapports v2 ajoute treize colonnes à `reports`, la table `report_feedback`, un
index unique partiel sur `credit_events` et `credit_balances.legacy_verifie_at`.

**Ordre obligatoire : migrer, PUIS redémarrer.** L'ancien code tolère des
colonnes en trop ; le nouveau lit des colonnes qui n'existent pas encore. Il
n'y a donc aucune fenêtre où l'ancien code casse, mais il y en a une où le
nouveau casse.

**Contrôle préalable obligatoire.** L'index unique partiel échoue s'il existe
déjà un doublon `premier_rapport_offert` — et, créé en `CONCURRENTLY` hors
transaction, il laisse derrière lui un index **INVALID** à supprimer à la main.
La migration dédoublonne elle-même (elle garde la ligne la plus ancienne), mais
il faut savoir ce qu'elle va supprimer :

```sql
-- À exécuter sur la base de PRODUCTION avant `alembic upgrade head`.
SELECT user_id, count(*)
FROM credit_events
WHERE action = 'premier_rapport_offert'
GROUP BY user_id HAVING count(*) > 1;
```

S'il reste un index invalide d'une tentative précédente :

```sql
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
DROP INDEX CONCURRENTLY ux_credit_events_premier_rapport_offert;
```

Nouvelles variables à poser dans Doppler (`prd`) avant le redémarrage :
`DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=20`, et `GOOGLE_CLIENT_ID` /
`GOOGLE_CLIENT_SECRET` si la livraison Google Drive doit apparaître.

## 4. Qdrant (binaire natif) + service
```bash
# le binaire bin/qdrant est déjà dans le repo (ou re-télécharge la release aarch64/x86_64 selon le VPS)
sudo cp deploy/axial-qdrant.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now axial-qdrant
```

## 5. Presidio (PII) via docker
```bash
docker run -d --restart always --name axial-presidio -p 127.0.0.1:8010:3000 \
  mcr.microsoft.com/presidio-analyzer   # (ou l'image utilisée par ton docker-compose local)
```
*(sinon, mets `PII_GUARD_MODE=off` pour démarrer sans Presidio et l'ajouter ensuite.)*

## 6. Base de connaissance (Qdrant, 491 Mo)
Depuis ton **Mac** (Qdrant local arrêté pour un snapshot cohérent, ou copie à chaud) :
```bash
rsync -avz data/qdrant-server/ axial@<IP_VPS>:/opt/axial-intelligence/data/qdrant-server/
sudo systemctl restart axial-qdrant
```
*(alternative : ré-ingérer sur le VPS avec `scripts/ingest_knowledge_base.py` ~2$.)*

## 7. Front (build avec l'URL API) + services

> **L'URL de l'API est figée dans le bundle à la compilation.** Un `npm run build`
> lancé sans `NEXT_PUBLIC_API_URL` fige `http://127.0.0.1:8090` et casse l'app
> pour tous les utilisateurs (vécu du 04 au 07/09/2026). Le `.env.local` du VPS
> porte désormais la valeur de production ; après chaque build, vérifier quand
> même : `grep -c '127.0.0.1:8090' .next/static/chunks/*.js` doit valoir 0, puis
> tester une inscription depuis un compte neuf dans le navigateur.

> **Deuxième variable depuis Rapports v2 : `API_INTERNE_URL`.** La page publique
> `/p/<pseudo>/<slug>` est rendue **côté serveur** : son `fetch` part du process
> Next, pas du navigateur. Sans cette variable il reprenait `NEXT_PUBLIC_API_URL`,
> donc le VPS faisait un aller-retour DNS + TLS + reverse proxy vers son propre
> nom public pour joindre un backend qui écoute sur `127.0.0.1:8090` — et la page
> cassait si le certificat ou le proxy avait un souci. Elle est lue à
> l'EXÉCUTION (pas de préfixe `NEXT_PUBLIC_`), donc elle va dans le `.env.local`
> du VPS et **pas** dans la ligne de build :
>
> ```
> # /opt/axial-intelligence/frontend/.env.local
> NEXT_PUBLIC_API_URL=https://app.axial-ia.fr/api
> API_INTERNE_URL=http://127.0.0.1:8090
> ```
>
> Les `<img>` des graphiques d'un rapport partagé gardent, elles, l'URL
> publique : c'est le navigateur du visiteur qui les charge.

```bash
cd /opt/axial-intelligence/frontend
NEXT_PUBLIC_API_URL=https://app.axial-ia.fr/api npm ci && \
NEXT_PUBLIC_API_URL=https://app.axial-ia.fr/api npm run build
# services backend / worker / front
sudo cp /opt/axial-intelligence/deploy/axial-backend.service /etc/systemd/system/
sudo cp /opt/axial-intelligence/deploy/axial-worker.service /etc/systemd/system/
sudo cp /opt/axial-intelligence/deploy/axial-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now axial-backend axial-worker axial-frontend
```

## 8. Reverse proxy

> **Lequel est en service ?** `deploy/` porte DEUX configurations —
> `deploy/nginx-axial.conf` (`app.axial-ia.fr`) et `deploy/Caddyfile`
> (`app.axial-ia.com`, coquille préexistante). C'est **nginx** qui sert la
> production ; le `Caddyfile` est un reliquat.

**Timeout — obligatoire depuis Rapports v2.** `POST /analysis/run` (le repli
bloquant du flux) tient la requête HTTP ouverte pendant TOUTE la génération,
jusqu'à 1800 s (`DELAI_MAX_RAPPORT_SECONDES`). À `proxy_read_timeout 300s`,
nginx rendait un **504** à cinq minutes sur un rapport de 32 000 tokens qui se
terminait normalement — et **était débité**. `deploy/nginx-axial.conf` porte
désormais `proxy_read_timeout 1800s` et `proxy_http_version 1.1` sur `/api/`
(HTTP/1.0 bufferise le SSE et le rend d'un seul bloc, à la fin).

Le flux SSE est protégé en plus par un battement (`: keepalive` toutes les 15 s,
`app/modules/analysis/service.py`) : le timeout est une borne, pas le mécanisme.

```bash
sudo cp /opt/axial-intelligence/deploy/nginx-axial.conf /etc/nginx/sites-available/axial
sudo nginx -t && sudo systemctl reload nginx
```

## 9. Stripe live
- Dashboard Stripe (Mode **Live**) → Developers → Webhooks → **Add endpoint** :
  `https://app.axial-ia.fr/api/billing/webhook`, événements `checkout.session.completed` + `invoice.paid`.
- Copie le **Signing secret** (`whsec_…` live) → `doppler secrets set STRIPE_WEBHOOK_SECRET --config prd`.
- Assure-toi que `STRIPE_API_KEY` en prd est la **clé live**.

## 10. Resend (emails)
- Resend → Domains → ajoute `axial-ia.fr` → pose les **SPF/DKIM** au DNS. Une fois vérifié, `MAIL_FROM=veille@axial-ia.fr` fonctionne.

## 11. Vérification e2e
- `https://app.axial-ia.fr` charge (HTTPS vert), l'ancienne app marche toujours.
- **Inscription réelle** → onboarding → une question dans Workspace renvoie une réponse sourcée.
- Onglet Agents : créer un agent, « Lancer maintenant » → run OK.
- Crédits → S'abonner (carte réelle, petit montant) → webhook live 200 → crédits crédités.
- Un agent avec email → email de veille reçu.

## Rollback rapide
`sudo systemctl stop axial-backend axial-worker axial-frontend` + retirer le bloc Caddy `app.axial-ia.fr` + reload caddy. L'ancienne app n'est jamais touchée.
