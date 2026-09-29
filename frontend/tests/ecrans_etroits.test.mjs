import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const css = readFileSync(join(racine, 'app/globals.css'), 'utf8');
const app = readFileSync(join(racine, 'app/_prototype/App.jsx'), 'utf8');

test('écrans étroits : un seul seuil, 1024 px, en CSS comme en JS', () => {
  assert.equal((css.match(/\(max-width: 767px\)/g) || []).length, 0, 'plus aucun 767 en CSS');
  assert.equal((css.match(/\(min-width: 768px\)/g) || []).length, 0, 'plus aucun 768 en CSS');
  assert.ok((css.match(/\(max-width: 1023px\)/g) || []).length >= 5);
  assert.match(app, /const LARGEUR_ETROITE_MAX = 1024;/);
  assert.match(app, /window\.innerWidth >= LARGEUR_ETROITE_MAX/);
  assert.doesNotMatch(app, /innerWidth >= 768\b/);
});

test('lot 2 : conversation lisible sur écran étroit', () => {
  const bloc = css.slice(css.indexOf('ÉCRANS ÉTROITS — revue téléphone'));
  assert.match(bloc, /\.composer-tip > span \{ display: none; \}/);
  assert.match(bloc, /\.empty-state \{ justify-content: flex-start; overflow-y: auto;/);
  assert.match(bloc, /\.topbar-title \.crumb, \.topbar-title \.crumb-sep \{ display: none; \}/);
  assert.match(app, /<span className="crumb-sep"> \/ <\/span>/);
  assert.match(app, /const CLE_BANDEAU_PROFIL = 'axial_bandeau_profil_ferme';/);
  assert.match(app, /\{profilVide && !profilFerme && \(/);
  assert.match(app, /className="ax-bandeau-profil-fermer"/);
});

test('lot 3 : landing, carte, composeur de rapport, bandeaux', () => {
  const bloc = css.slice(css.indexOf('ÉCRANS ÉTROITS — revue téléphone'));
  assert.match(bloc, /\.landing-nav-links \{ display: none; \}/);
  assert.match(bloc, /\.first-action-card \.btn-lg \{ width: 100%;/);
  assert.match(bloc, /\.rep-prompt-foot \{ flex-direction: column;/);
  assert.match(bloc, /\.rep-templates \{\s*-webkit-mask-image/);
  // Les bandeaux ne changent plus la forme de l'arbre : pas de remontage.
  assert.match(app, /const avecBandeau = \(ecran\) => <>\{bandeauVersion\}\{bandeauConsentement\}\{ecran\}<\/>;/);
});
