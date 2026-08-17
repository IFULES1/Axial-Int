# Paramétrage Resend (envoi des emails de veille)

Bonne nouvelle : **Resend expose un endpoint SMTP**, donc il se branche sur notre code
`email.py` existant **sans changement de code** — juste 5 secrets Doppler.

## Étapes

### 1. Créer le compte
- S'inscrire sur **resend.com** (offre gratuite : ~3 000 emails/mois, 100/jour — large pour la veille).

### 2. Choisir l'expéditeur (2 options)
- **Test rapide** : utiliser le domaine bac à sable `onboarding@resend.dev` (aucune config DNS, mais n'envoie qu'à ta propre adresse vérifiée).
- **Production** : ajouter **ton domaine** (`axial-ia.fr`) dans Resend → il te donne des enregistrements **DNS** (SPF, DKIM, éventuellement DMARC) à poser chez ton registrar/hébergeur DNS. Une fois vérifié, tu peux envoyer depuis `veille@axial-ia.fr`.

### 3. Créer une clé API
- Dashboard Resend → **API Keys** → *Create* → copier la clé (commence par `re_…`).

### 4. Poser les secrets dans Doppler
Resend SMTP : hôte `smtp.resend.com`, port `587`, utilisateur littéral `resend`, mot de passe = la clé API.
```bash
doppler secrets set SMTP_HOST="smtp.resend.com" SMTP_PORT="587" SMTP_USER="resend" SMTP_FROM="veille@axial-ia.fr"
# le mot de passe (= clé API) : à faire toi-même
doppler secrets set SMTP_PASSWORD
# (colle la clé re_... quand il la demande)
```
> En test, mettre `SMTP_FROM="onboarding@resend.dev"` et n'envoyer qu'à ta propre adresse.

### 5. Redémarrer
```bash
# backend
lsof -tiTCP:8090 -sTCP:LISTEN | xargs kill ; doppler run -- .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090 &
# worker
pkill -f worker.main ; doppler run -- .venv/bin/python -m worker.main &
```

### 6. Tester
- Créer un agent de veille avec ton email dans `email_recipients`, cliquer **Lancer maintenant**, vérifier la réception.
- Le mail est envoyé en **HTML** (rendu de `email.py` — delta + rapport), fallback texte.

## Notes
- Le code `app/modules/watches/email.py` est déjà prêt (SMTP + HTML). Rien à modifier.
- Si un jour tu veux l'API native Resend (plutôt que SMTP) pour les webhooks/tracking, ce serait un petit ajout — mais le SMTP suffit largement pour la veille.
- Alternatives équivalentes si besoin : Brevo, Mailgun, Amazon SES (tous exposent aussi du SMTP → même branchement).
