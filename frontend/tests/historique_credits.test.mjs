import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

test('historique des crédits : rapport offert libellé, échecs techniques masqués', () => {
  const app = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'app/_prototype/App.jsx'), 'utf8');
  assert.match(app, /premier_rapport_offert: lang === 'fr' \? 'Rapport offert'/);
  assert.match(app, /EVENEMENTS_MASQUES = new Set\(\['premier_rapport_echec'\]\)/);
  assert.match(app, /events\.filter\(\(e\) => !EVENEMENTS_MASQUES\.has\(e\.action\)\)\.slice\(0, 30\)/);
});
