// Garde-fou contre le bug de la Task 7 (F1) : `axCoutConversation` était
// APPELÉ dans App.jsx sans figurer dans sa liste d'import de `./bridge`. Ni
// `next build` ni les tests ne le voyaient — un identifiant libre se compile
// sans bruit et ne lève son `ReferenceError` qu'à l'exécution, dans un `try`
// qui le transformait en carte d'erreur à chaque réponse réussie.
//
// Ce test relit App.jsx, extrait la liste `import { … } from './bridge'`, puis
// vérifie que CHAQUE identifiant `ax…(` appelé dans le fichier est soit importé
// du bridge, soit défini localement (fonction, const, let, var, paramètre de
// fonction fléchée, propriété d'objet), soit lu sur `window`.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const cheminApp = join(racine, 'app/_prototype/App.jsx');
const cheminBridge = join(racine, 'app/_prototype/bridge.js');
const app = readFileSync(cheminApp, 'utf8');
const bridge = readFileSync(cheminBridge, 'utf8');

/* La liste d'import du bridge, telle qu'elle est écrite dans App.jsx. */
function importsDuBridge(source) {
  const m = source.match(/import\s*\{([\s\S]*?)\}\s*from\s*["']\.\/bridge["']/);
  assert.ok(m, "App.jsx doit importer depuis './bridge'");
  return new Set(
    m[1].split(',')
      .map((s) => s.trim().split(/\s+as\s+/).pop().trim())
      .filter(Boolean),
  );
}

/* Tout identifiant `axQuelqueChose` suivi d'une parenthèse = un appel. */
function appelsAx(source) {
  const trouves = new Set();
  const re = /\bax[A-Z]\w*(?=\s*\()/g;
  let m;
  while ((m = re.exec(source)) !== null) trouves.add(m[0]);
  return trouves;
}

/* Définitions locales : `function axX(`, `const axX =`, `axX:` (méthode d'objet
   ou propriété), et les identifiants lus sur `window.axX`. */
function definitionsLocales(source) {
  const trouves = new Set();
  const motifs = [
    /\b(?:function|const|let|var|class)\s+(ax[A-Z]\w*)/g,
    /\b(ax[A-Z]\w*)\s*:/g,
    /\bwindow\.(ax[A-Z]\w*)/g,
  ];
  for (const re of motifs) {
    let m;
    while ((m = re.exec(source)) !== null) trouves.add(m[1]);
  }
  return trouves;
}

test("tout appel ax…() d'App.jsx est importé du bridge ou défini localement", () => {
  const importes = importsDuBridge(app);
  const locaux = definitionsLocales(app);
  const manquants = [...appelsAx(app)].filter((n) => !importes.has(n) && !locaux.has(n)).sort();
  assert.deepEqual(manquants, [],
    `identifiant(s) ax…() appelé(s) dans App.jsx sans import ni définition locale : ${manquants.join(', ')}`);
});

test('chaque identifiant importé de ./bridge y est bien exporté', () => {
  const exportes = new Set();
  const re = /\bexport\s+(?:async\s+)?(?:function|const|let|var|class)\s+(\w+)/g;
  let m;
  while ((m = re.exec(bridge)) !== null) exportes.add(m[1]);
  const manquants = [...importsDuBridge(app)].filter((n) => !exportes.has(n)).sort();
  assert.deepEqual(manquants, [],
    `importé(s) d'App.jsx mais absent(s) des exports de bridge.js : ${manquants.join(', ')}`);
});

test('axCoutConversation : importé, et branché sur GET …/cout', () => {
  // Cas nommé de la régression : on verrouille l'import ET la route.
  assert.ok(importsDuBridge(app).has('axCoutConversation'),
    'axCoutConversation doit figurer dans la liste d\'import de ./bridge');
  assert.match(bridge, /export\s+async\s+function\s+axCoutConversation/);
  assert.match(bridge, /\/intelligence\/conversations\/\$\{cid\}\/cout/);
});
