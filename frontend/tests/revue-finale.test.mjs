// Garde-fous de la revue finale de branche (findings 8, 9, 10).
//
// Ces trois corrections sont invisibles à l'exécution : un prix recopié en dur
// reste affiché, une règle CSS morte ne casse rien, un `'⚠️ ' + e.message`
// s'affiche. Seule une relecture du fichier les empêche de revenir.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(racine, 'app/_prototype/App.jsx'), 'utf8');
const css = readFileSync(join(racine, 'app/globals.css'), 'utf8');

/* Les deux dictionnaires, extraits du littéral `STRINGS`. */
function cles(langue) {
  const debut = app.indexOf(`  ${langue}: {`);
  assert.ok(debut > 0, `dictionnaire ${langue} introuvable`);
  const fin = app.indexOf('\n  },', debut);
  const bloc = app.slice(debut, fin);
  const trouvees = new Map();
  const re = /^\s{4}'([^']+)':\s*(.*)$/gm;
  let m;
  while ((m = re.exec(bloc)) !== null) trouvees.set(m[1], m[2]);
  return trouvees;
}

test('finding 8 — le prix d’un message a UNE seule source', () => {
  assert.match(app, /const CREDITS_PAR_MESSAGE = \d+;/);
  // Une seule déclaration : la valeur était définie deux fois dans le fichier.
  assert.equal((app.match(/const CREDITS_PAR_MESSAGE =/g) || []).length, 1);

  for (const langue of ['fr', 'en']) {
    const dico = cles(langue);
    for (const cle of ['credits.modale.detail', 'err.credits.detail',
                       'conv.regenerer.aide', 'conv.editer.aide']) {
      const texte = dico.get(cle);
      assert.ok(texte, `${langue}/${cle} manquante`);
      assert.ok(texte.includes('{credits}'),
        `${langue}/${cle} doit écrire {credits}, pas le prix en dur : ${texte}`);
      assert.ok(!/\b2 (crédits|credits)\b/.test(texte),
        `${langue}/${cle} porte encore « 2 crédits » en dur`);
    }
  }
  // La substitution est faite à la lecture du dictionnaire, dans les DEUX
  // accesseurs (`texteI18n` sert les branches rendues avant les hooks).
  assert.match(app, /function texteI18n\(cle\) \{[\s\S]{0,200}_avecCredits\(/);
  assert.match(app, /window\.useT =[\s\S]{0,600}_avecCredits\(/);
});

test('parité FR/EN maintenue, clés de facturation comprises', () => {
  const fr = cles('fr');
  const en = cles('en');
  assert.deepEqual([...fr.keys()].filter((k) => !en.has(k)), []);
  assert.deepEqual([...en.keys()].filter((k) => !fr.has(k)), []);
  for (const cle of ['err.facturation.titre', 'err.facturation.detail']) {
    assert.ok(fr.has(cle) && en.has(cle), `${cle} doit exister en FR et EN`);
  }
  // Le code renvoyé par le backend est bien nommé côté front.
  assert.match(app, /code === 'facturation_echec'/);
});

test('finding 9 — plus de CSS pour du markup inexistant', () => {
  for (const classe of ['credits-chart', 'credits-chart-card', 'credits-bar',
                        'quota-bar-row', 'rep-editor']) {
    assert.ok(!app.includes(classe),
      `.${classe} est rendue quelque part : la règle CSS ne doit pas partir`);
    // Plus aucun SÉLECTEUR : les commentaires qui expliquent le retrait
    // peuvent citer le nom, une règle non.
    const selecteurs = (css.match(new RegExp(`^[^/*\\n]*\\.${classe}[^\\n]*\\{`, 'gm')) || []);
    assert.deepEqual(selecteurs, [], `règle CSS résiduelle pour .${classe}`);
  }
});

test('finding 10 — plus aucun message d’exception brut dans l’interface', () => {
  // Le pictogramme concaténé à un message d'exception, hors commentaires (les
  // commentaires du fichier citent le motif pour expliquer pourquoi il est
  // parti).
  const codeSeul = app.split('\n')
    .filter((l) => !/^\s*(\/\/|\/\*|\*)/.test(l))
    .join('\n');
  assert.ok(!/'⚠️ ?' ?\+/.test(codeSeul),
    "un `⚠️ + e.message` est de retour : passer par `decrireErreur`");
  assert.ok(!/⚠️[^\n]*e\.message/.test(codeSeul));
  // Le chemin des rapports rend désormais la carte d'erreur du fil.
  assert.match(app, /reportsState === 'erreur'[\s\S]{0,400}<CarteErreur/);
});
