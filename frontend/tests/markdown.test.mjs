// Tests du parseur markdown maison (frontend/app/_prototype/markdown.js).
// `npm test` → `node --test tests/`.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parserMarkdown } from '../app/_prototype/markdown.js';

test('texte brut sans markdown : un paragraphe, un nœud texte', () => {
  const blocs = parserMarkdown('Bonjour, voici une phrase simple sans balisage.');
  assert.equal(blocs.length, 1);
  assert.equal(blocs[0].type, 'paragraph');
  assert.equal(blocs[0].inline.length, 1);
  assert.equal(blocs[0].inline[0].type, 'text');
  assert.equal(blocs[0].inline[0].text, 'Bonjour, voici une phrase simple sans balisage.');
});

test('texte vide : aucun bloc', () => {
  assert.deepEqual(parserMarkdown(''), []);
  assert.deepEqual(parserMarkdown(null), []);
});

test('titres # ## ###', () => {
  const blocs = parserMarkdown('# Titre 1\n## Titre 2\n### Titre 3');
  assert.deepEqual(blocs.map((b) => [b.type, b.level]), [
    ['heading', 1], ['heading', 2], ['heading', 3],
  ]);
  assert.equal(blocs[0].inline[0].text, 'Titre 1');
});

test('gras et italique', () => {
  const blocs = parserMarkdown('Un mot **important** et un mot *nuancé*.');
  const inline = blocs[0].inline;
  const strong = inline.find((n) => n.type === 'strong');
  const em = inline.find((n) => n.type === 'em');
  assert.ok(strong);
  assert.equal(strong.children[0].text, 'important');
  assert.ok(em);
  assert.equal(em.children[0].text, 'nuancé');
});

test('code inline', () => {
  const blocs = parserMarkdown('Utilisez la fonction `parserMarkdown()` ici.');
  const code = blocs[0].inline.find((n) => n.type === 'code');
  assert.ok(code);
  assert.equal(code.text, 'parserMarkdown()');
});

test('lien [texte](url)', () => {
  const blocs = parserMarkdown('Voir [la doc](https://axial-ia.fr/docs) pour plus.');
  const lien = blocs[0].inline.find((n) => n.type === 'link');
  assert.ok(lien);
  assert.equal(lien.href, 'https://axial-ia.fr/docs');
  assert.equal(lien.children[0].text, 'la doc');
});

test('citation [N] conservée comme nœud cite', () => {
  const blocs = parserMarkdown('Une affirmation sourcée [3].');
  const cite = blocs[0].inline.find((n) => n.type === 'cite');
  assert.ok(cite);
  assert.equal(cite.n, 3);
});

test('liste à puces simple', () => {
  const blocs = parserMarkdown('- premier\n- deuxième\n- troisième');
  assert.equal(blocs.length, 1);
  assert.equal(blocs[0].type, 'list');
  assert.equal(blocs[0].ordered, false);
  assert.equal(blocs[0].items.length, 3);
  assert.equal(blocs[0].items[1].inline[0].text, 'deuxième');
});

test('liste numérotée', () => {
  const blocs = parserMarkdown('1. étape un\n2. étape deux\n3. étape trois');
  assert.equal(blocs[0].type, 'list');
  assert.equal(blocs[0].ordered, true);
  assert.equal(blocs[0].items.length, 3);
  assert.equal(blocs[0].items[2].inline[0].text, 'étape trois');
});

test('liste avec un niveau d\'imbrication (puces)', () => {
  const blocs = parserMarkdown('- parent 1\n  - enfant 1a\n  - enfant 1b\n- parent 2');
  const liste = blocs[0];
  assert.equal(liste.items.length, 2);
  assert.ok(liste.items[0].children);
  assert.equal(liste.items[0].children.length, 2);
  assert.equal(liste.items[0].children[0].inline[0].text, 'enfant 1a');
  assert.ok(!liste.items[1].children);
});

test('liste numérotée avec sous-liste numérotée imbriquée', () => {
  const blocs = parserMarkdown('1. étape un\n  1. sous-étape a\n  2. sous-étape b\n2. étape deux');
  const liste = blocs[0];
  assert.equal(liste.items[0].children.length, 2);
  assert.equal(liste.items[0].children[0].ordered, true);
});

test('bloc de code avec langue', () => {
  const blocs = parserMarkdown('```js\nconst x = 1;\nconsole.log(x);\n```');
  assert.equal(blocs.length, 1);
  assert.equal(blocs[0].type, 'code');
  assert.equal(blocs[0].lang, 'js');
  assert.equal(blocs[0].code, 'const x = 1;\nconsole.log(x);');
});

test('bloc de code sans langue', () => {
  const blocs = parserMarkdown('```\nplain text block\n```');
  assert.equal(blocs[0].type, 'code');
  assert.equal(blocs[0].lang, '');
});

test('citation > sur plusieurs lignes, analysée récursivement', () => {
  const blocs = parserMarkdown('> Première ligne citée\n> **Deuxième** ligne citée');
  assert.equal(blocs.length, 1);
  assert.equal(blocs[0].type, 'quote');
  assert.equal(blocs[0].blocks.length, 2);
  assert.equal(blocs[0].blocks[0].type, 'paragraph');
  assert.ok(blocs[0].blocks[1].inline.some((n) => n.type === 'strong'));
});

test('séparateur --- et ***', () => {
  const blocs = parserMarkdown('texte avant\n---\ntexte après\n***\nfin');
  const types = blocs.map((b) => b.type);
  assert.deepEqual(types, ['paragraph', 'hr', 'paragraph', 'hr', 'paragraph']);
});

test('tableau simple', () => {
  const texte = '| Nom | Valeur |\n|---|---|\n| Alpha | 1 |\n| Beta | 2 |';
  const blocs = parserMarkdown(texte);
  assert.equal(blocs.length, 1);
  assert.equal(blocs[0].type, 'table');
  assert.equal(blocs[0].header.length, 2);
  assert.equal(blocs[0].header[0][0].text, 'Nom');
  assert.equal(blocs[0].rows.length, 2);
  assert.equal(blocs[0].rows[0][0][0].text, 'Alpha');
});

test('bloc ```viz conservé tel quel', () => {
  const texte = '```viz\n{"type":"bar","series":[{"label":"A","value":1}]}\n```';
  const blocs = parserMarkdown(texte);
  assert.equal(blocs.length, 1);
  assert.equal(blocs[0].type, 'viz');
  assert.equal(blocs[0].closed, true);
  assert.equal(blocs[0].raw, '{"type":"bar","series":[{"label":"A","value":1}]}');
});

test('bloc ```viz non fermé (flux en cours) : closed=false', () => {
  const texte = '```viz\n{"type":"bar"';
  const blocs = parserMarkdown(texte);
  assert.equal(blocs[0].type, 'viz');
  assert.equal(blocs[0].closed, false);
});

test('mélange tableau + viz + liste numérotée dans un même texte', () => {
  const texte = [
    '## Analyse',
    '',
    '| Année | CA |',
    '|---|---|',
    '| 2024 | 100 |',
    '| 2025 | 140 |',
    '',
    '```viz',
    '{"type":"bar","series":[{"label":"2024","value":100},{"label":"2025","value":140}]}',
    '```',
    '',
    '1. Croissance de 40%',
    '2. Portée par le segment SaaS',
  ].join('\n');
  const blocs = parserMarkdown(texte);
  const types = blocs.map((b) => b.type);
  assert.deepEqual(types, ['heading', 'table', 'viz', 'list']);
  assert.equal(blocs[1].rows.length, 2);
  assert.equal(blocs[2].closed, true);
  assert.equal(blocs[3].items.length, 2);
  assert.equal(blocs[3].ordered, true);
});

test('citations multiples [N][M] sur la même ligne', () => {
  const blocs = parserMarkdown('Deux sources se recoupent [1][2].');
  const cites = blocs[0].inline.filter((n) => n.type === 'cite');
  assert.equal(cites.length, 2);
  assert.deepEqual(cites.map((c) => c.n), [1, 2]);
});

test('plusieurs paragraphes distincts (une ligne = un paragraphe)', () => {
  const blocs = parserMarkdown('Première ligne.\nDeuxième ligne.');
  assert.equal(blocs.length, 2);
  assert.equal(blocs[0].type, 'paragraph');
  assert.equal(blocs[1].type, 'paragraph');
});
