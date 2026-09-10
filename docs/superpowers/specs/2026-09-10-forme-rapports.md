# Forme des rapports — spécification (retours de Christian, 25/08/2026)

## Origine

Christian (EQON Nexus, `christian@eqonx.com`) a produit deux études de marché
et écrit : *« would be useful if the tables were properly formatted, included
some graphs for market metrics, if the citation numbers hyperlinked to the
references… and also if there was an executive summary »*.

## Constat sur le code (10/09/2026)

| Demande | Dans l'app | Dans le PDF |
|---|---|---|
| Tableaux markdown | `MarkdownView` ne connaît pas les lignes `\|` : elles sortent en paragraphes bruts | `render_pdf` ignore les tableaux : lignes brutes |
| Citations `[N]` cliquables | cliquables dans le chat (`onCite`) mais **pas** dans l'éditeur de rapport (`<MarkdownView text={content} />` sans `onCite`) | texte inerte, aucune section Sources générée depuis `report.sources` |
| Synthèse exécutive en tête | seule `synthese_executive` l'exige (`special_instructions`) | idem |
| Graphiques | aucun | aucun |

Le prompt (`STYLE DE RÉDACTION`, règle 5) autorise déjà 1 à 3 tableaux ; le
modèle en produit. Ils sont donc **déjà dans le contenu**, simplement pas
rendus.

## Exigences

1. **Tableaux** : un bloc de lignes commençant par `|` est rendu en table dans
   l'app (HTML) et dans le PDF (ReportLab `Table`). La ligne de séparation
   `|---|` est ignorée. Cellules : gras et citations rendus comme ailleurs.
2. **Citations** : dans l'éditeur de rapport, cliquer `[N]` fait défiler vers la
   source N de la liste sous le rapport. Dans le PDF, `[N]` devient un lien
   interne vers l'entrée N d'une section « Sources » générée depuis
   `report.sources` (titre + domaine + URL cliquable).
3. **Synthèse exécutive** : chaque rapport commence par `## Synthèse exécutive`
   (ou `## Executive summary` en anglais) : 5 à 8 phrases, chiffres clés
   inclus, avant la section 1. Règle ajoutée au bloc `STYLE DE RÉDACTION`.
   **Changement de contenu produit → diff montré à Miradie avant déploiement.**
4. **Graphiques (réserve assumée)** : uniquement à partir d'un tableau dont
   toutes les cellules hors première colonne sont numériques et de même
   unité (détectée par un suffixe commun : `%`, `M€`, `Md€`, `k`). Rendu en
   barres dans le PDF, sous le tableau, jamais à la place. Aucun graphique
   n'est inventé à partir de la prose. Hors de ce cas, rien.

## Hors périmètre

- Modifier la structure des sections des rapports au-delà de la synthèse.
- Graphiques dans l'app (le PDF est le livrable partagé ; l'app suit si le
  besoin est confirmé).
- Reprendre les 42 rapports déjà archivés (ils se rendent avec le nouveau
  moteur à l'ouverture, sans régénération).

## Contraintes globales

- Python 3.12 (VPS) / 3.13 (local), ReportLab ≥ 4.2 déjà installé.
- Le PDF garde le filigrane (`_draw_watermark`) et les polices standard.
- `render_pdf(title, markdown, sources=None)` : le paramètre est optionnel,
  les appels existants ne cassent pas.
- Tests : `.venv/bin/pytest tests/ -q` vert, `.venv/bin/ruff check app tests`
  propre. Front : `npm run build` puis vérifier
  `grep -c '127.0.0.1:8090' .next/static/chunks/*.js` = 0 (voir `docs/DEPLOY.md`).
- Déploiement : scp fichier par fichier, `systemctl restart axial-backend`,
  rebuild front, `systemctl restart axial-frontend`.
