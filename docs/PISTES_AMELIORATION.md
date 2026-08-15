# Pistes d'amélioration — Axial Intelligence

> Backlog des évolutions décidées ou identifiées. À rappeler à l'utilisateur au fil de l'eau.

## 🔴 Prioritaire / engagé

### Embeddings : Cohere payant → migrer vers BGE-m3 auto-hébergé (À FAIRE PLUS TARD)
- **Décision (2026-08-13)** : on part sur **B = Cohere payant** maintenant (rapide, ~1 $ one-time + ~1-3 $/mois)
  pour débloquer l'ingestion et finir le bout-en-bout.
- **Bascule prévue vers C = BGE-m3 auto-hébergé** quand le moment sera venu :
  - **Pourquoi** : coût **0 €** pour toujours, **aucune limite de débit**, et surtout **les documents ne quittent
    jamais l'infra** → argument **RGPD / souveraineté**, potentiellement **commercial** pour du B2B européen.
  - **Coût de la bascule** : ~1h-1h30 (adaptateur embeddings BGE + lib sentence-transformers + ~2 Go modèle +
    re-vectorisation). Déploiement un peu plus lourd (RAM/CPU VPS).
  - **⚠️ Contrainte** : l'embedding doit être **le même modèle pour la base ET les requêtes** → la bascule = re-vectoriser
    tout le corpus (nouvelle collection Qdrant à la bonne dimension). Le code est provider-agnostique (`embedding_provider`),
    donc c'est une bascule propre.
  - **👉 RAPPEL À FAIRE** : reproposer cette bascule quand (a) la souveraineté devient un argument de vente, ou
    (b) le volume/coût Cohere grimpe, ou (c) avant la mise en prod « données clients ».

### Durcissement sécurité VPS (prod insight-map, avant go-live Axial)
- SSH : `PasswordAuthentication no` + installer **fail2ban** (brute-force actif constaté).
- `chmod 600 .env` + supprimer les `.env.bak`.
- **Révoquer la clé Perplexity fuitée** dans l'ancien repo.

## 🟠 Avant la prod

- **Doppler config `prd`** : dupliquer les secrets en prod (clés séparées dev/prod), service token sur le VPS.
- **Auth prod** : trancher (garder Supabase + Pro / Clerk / GoTrue auto-hébergé). Le mode local reste dev-only.
  → 1 test d'intégration du chemin `AUTH_MODE=supabase` + flux emails avant go-live.
- **Qdrant prod** : passer d'un embedded sur disque (mono-process) à un **vrai serveur Qdrant** (multi-process).
- **Supabase Analytics** : hébergement toujours différé (limite 2 projets gratuits). Schéma prêt (`app/modules/analytics/schema.sql`).

## 🟡 Produit / qualité

- **Fine-tuning** (discuté, reporté) : quand le volume d'analyses réelles sera là, construire un dataset
  (question → analyse idéale) depuis les meilleurs rapports + distillation, fine-tuner pour le style/méthodo Axial.
  → Ajouter dès que possible la **capture dataset** (logger entrées+sorties+feedback de chaque analyse).
- **Preview/paywall** (`pending_reports`) : mécanisme d'aperçu gratuit avant déverrouillage par crédits — non réimplémenté (simplifié).
- **Extraction KB** : ajouter **DOCX/XLSX** + **OCR** (des PDF scannés ont été ignorés à l'ingestion).
- **Optimisations coût LLM** : **prompt caching** (-90 % sur le system prompt répété) + **Batch API** (-50 %) pour le worker asynchrone (veilles/agents).

## 🟢 Cycle de vie modèles (garde-fou)
- LLM chat = **`gemini-flash-latest`** (auto-suit le dernier Flash → immunisé contre les retraits). ✅
- Rappel calendrier : Gemini 2.5 retiré le **16/10/2026** ; Claude Sonnet repasse à 3$/15$ le **01/09/2026** (impact = quelques centimes/rapport).
- Ajouter un **`/health/providers`** qui pingue chaque modèle configuré (détecte un retrait avant les users).

---
_Historique_ : créé le 2026-08-13. Décision embeddings B→C actée le 2026-08-13.
