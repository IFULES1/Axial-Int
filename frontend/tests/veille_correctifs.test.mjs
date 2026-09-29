import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(racine, 'app/_prototype/App.jsx'), 'utf8');
const bridge = readFileSync(join(racine, 'app/_prototype/bridge.js'), 'utf8');

// Correctifs du bilan veille du 29/09 —
// docs/superpowers/specs/2026-09-29-bilan-veilles.md
// Assertions booléennes : une regex qui échoue sur un fichier de 700 ko rend
// un diff illisible.

test('#18 — les skills viennent de l\'API, plus de liste recopiée dans l\'assistant', () => {
  assert.ok(app.includes('axWatchSkills()'),
    'la route /watches/skills existait et n\'était jamais appelée');
  assert.ok(!app.includes("{ id: 'produit_tech', t: lang === 'fr' ? 'Produit & tech'"),
    'la liste en dur doit disparaître : ajouter un skill au backend doit suffire');
});

test('#5 — un agent peut être supprimé depuis l\'app', () => {
  assert.ok(bridge.includes('export async function axDeleteWatch'));
  assert.ok(app.includes('axDeleteWatch('),
    'la route et le helper existaient, aucun bouton ne les appelait');
});

test('#4 — un agent peut être renommé et modifié', () => {
  assert.ok(bridge.includes('export async function axUpdateWatch'), 'helper PATCH manquant');
  assert.ok(bridge.includes('method: "PATCH"'), 'le helper doit appeler PATCH');
  assert.ok(app.includes('axUpdateWatch('), 'aucun écran n\'appelle la modification');
});

test('#1 — un agent sans crédits le dit sur sa carte', () => {
  assert.ok(app.includes('sans_credits'), 'le statut doit être rendu, pas affiché « actif »');
  assert.ok(app.includes("'agents.status.sans_credits'"), 'libellé manquant');
});

test('#7 — le détail d\'un run montre ses sources', () => {
  assert.ok(app.includes('shown.sources'),
    'le champ est renvoyé par l\'API et n\'était jamais affiché');
});

test('#10 — un run sans article RSS le signale', () => {
  assert.ok(app.includes('rss_utilise'), 'rien ne distinguait une veille d\'une recherche web');
});

test('#22 — plus de clés i18n orphelines côté agents', () => {
  for (const cle of ['agents.confidence', 'agents.last_finding', 'agents.sources',
                     'agents.wizard.trigger', 'agents.status.idle']) {
    assert.ok(!app.includes(`'${cle}'`), `${cle} n'est utilisée nulle part`);
  }
});
