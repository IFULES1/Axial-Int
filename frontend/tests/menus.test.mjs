// Garde-fou du 14/09 : les menus ⋯ / Exporter / Livrer se fermaient au
// `mousedown` avant le `click` de leurs éléments. Next monte React sur
// `document`, où vit aussi l'écouteur de fermeture : un `stopPropagation`
// React n'y change rien. La seule protection fiable est l'attribut
// `data-ax-menu` sur le menu lui-même, que l'écouteur ignore.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(racine, 'app/_prototype/App.jsx'), 'utf8');

test('chaque menu déroulant porte data-ax-menu', () => {
  const menus = [...app.matchAll(/<div className="ax-menu( ax-menu-droite)?"[^>]*>/g)].map((m) => m[0]);
  assert.ok(menus.length >= 2, 'au moins les menus ⋯ et Exporter/Livrer');
  for (const balise of menus) {
    assert.match(balise, /data-ax-menu="1"/, `menu sans garde : ${balise}`);
    assert.doesNotMatch(balise, /onMouseDown/, `garde illusoire (stopPropagation) : ${balise}`);
  }
});

test("l'écouteur de fermeture ignore les cibles sous data-ax-menu", () => {
  const gardes = app.match(/cible\.closest\('\[data-ax-menu\]'\)\) return;/g) || [];
  assert.ok(gardes.length >= 3, `${gardes.length} écouteurs gardés, 3 attendus (conversations, rapports, MenuBouton)`);
});
