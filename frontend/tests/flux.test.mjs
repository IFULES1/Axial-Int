// Task 2 (ciblage-investisseurs-v2 §3) : flux RSS visibles sur la carte
// d'un agent, testés. Couvre : `axWatchFeeds` dans bridge.js, les clés
// i18n `agents.flux.*` (parité FR/EN), et l'appel depuis la carte d'agent.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(racine, 'app/_prototype/App.jsx'), 'utf8');
const bridge = readFileSync(join(racine, 'app/_prototype/bridge.js'), 'utf8');

/* Extrait le corps d'une fonction top-level `function nom(...) { … }` par
 * comptage d'accolades (même utilitaire que kb.test.mjs). */
function extraireFonction(source, nom) {
  const debut = source.indexOf(`function ${nom}(`);
  assert.ok(debut >= 0, `function ${nom} introuvable dans le source`);
  // La liste de paramètres peut elle-même contenir des accolades
  // (déstructuration, ex. `{ agentId, onGererFlux }`) : on saute d'abord la
  // liste de paramètres (comptage de parenthèses) avant de chercher le `{`
  // qui ouvre le corps de la fonction.
  const parenOuvre = source.indexOf('(', debut);
  let profondeurParen = 0;
  let curseur = parenOuvre;
  for (; curseur < source.length; curseur++) {
    if (source[curseur] === '(') profondeurParen++;
    else if (source[curseur] === ')') {
      profondeurParen--;
      if (profondeurParen === 0) { curseur++; break; }
    }
  }
  const ouvre = source.indexOf('{', curseur);
  assert.ok(ouvre >= 0);
  let profondeur = 0;
  let i = ouvre;
  for (; i < source.length; i++) {
    if (source[i] === '{') profondeur++;
    else if (source[i] === '}') {
      profondeur--;
      if (profondeur === 0) { i++; break; }
    }
  }
  return { corps: source.slice(debut, i), debut, fin: i };
}

function extraireDict(source, lang) {
  const marqueur = `\n  ${lang}: {`;
  const iMarqueur = source.indexOf(marqueur);
  assert.ok(iMarqueur >= 0, `bloc STRINGS.${lang} introuvable`);
  const ouvre = source.indexOf('{', iMarqueur);
  let profondeur = 0;
  let i = ouvre;
  for (; i < source.length; i++) {
    if (source[i] === '{') profondeur++;
    else if (source[i] === '}') {
      profondeur--;
      if (profondeur === 0) { i++; break; }
    }
  }
  return source.slice(ouvre, i);
}

function clesDuDict(bloc) {
  const trouves = new Set();
  const re = /'([\w.]+)':/g;
  let m;
  while ((m = re.exec(bloc)) !== null) trouves.add(m[1]);
  return trouves;
}

// --- bridge.js ---------------------------------------------------------

test('bridge.js : axWatchFeeds → GET /watches/${id}/feeds', () => {
  const m = bridge.match(/export\s+async\s+function\s+axWatchFeeds\s*\([^)]*\)\s*\{[\s\S]*?\n\}/);
  assert.ok(m, 'axWatchFeeds introuvable dans bridge.js');
  assert.match(m[0], /`\/watches\/\$\{id\}\/feeds`/);
});

// --- import + usage dans App.jsx ----------------------------------------

test("App.jsx importe axWatchFeeds depuis ./bridge", () => {
  const m = app.match(/import\s*\{([^{}]*?)\}\s*from\s*["']\.\/bridge["']/);
  assert.ok(m, "App.jsx doit importer depuis './bridge'");
  const importes = new Set(m[1].split(',').map((s) => s.trim()));
  assert.ok(importes.has('axWatchFeeds'), 'axWatchFeeds doit être importé d\'App.jsx');
});

test('AgentFeedsLine appelle bien axWatchFeeds(agentId)', () => {
  const { corps } = extraireFonction(app, 'AgentFeedsLine');
  assert.match(corps, /axWatchFeeds\s*\(\s*agentId\s*\)/);
});

test("la carte d'un agent monte AgentFeedsLine avec l'id de l'agent", () => {
  const { corps } = extraireFonction(app, 'AgentsLibrary');
  assert.match(corps, /<AgentFeedsLine\s+agentId=\{a\.id\}/);
});

test('AgentFeedsLine ouvre la modale « Gérer mes flux » existante (FeedsManager) via setShowFeeds', () => {
  const { corps } = extraireFonction(app, 'AgentsLibrary');
  assert.match(corps, /onGererFlux=\{\(\)\s*=>\s*setShowFeeds\(true\)\}/);
});

// --- i18n ----------------------------------------------------------------

test("les clés agents.flux.* existent en FR et en EN, avec le même ensemble", () => {
  const fr = clesDuDict(extraireDict(app, 'fr'));
  const en = clesDuDict(extraireDict(app, 'en'));
  const clesFr = [...fr].filter((k) => k.startsWith('agents.flux.')).sort();
  const clesEn = [...en].filter((k) => k.startsWith('agents.flux.')).sort();
  assert.ok(clesFr.length > 0, 'aucune clé agents.flux.* trouvée en FR');
  assert.deepEqual(clesFr, clesEn,
    'les clés agents.flux.* doivent être strictement identiques entre FR et EN');
});

test('agents.flux.count porte le gabarit {n} en FR et EN', () => {
  const fr = extraireDict(app, 'fr');
  const en = extraireDict(app, 'en');
  assert.match(fr, /'agents\.flux\.count':\s*'[^']*\{n\}[^']*'/);
  assert.match(en, /'agents\.flux\.count':\s*'[^']*\{n\}[^']*'/);
});

test('les 3 états de flux (ok/erreur/inconnu) ont une clé i18n', () => {
  for (const etat of ['ok', 'erreur', 'inconnu']) {
    const cle = `'agents.flux.etat.${etat}':`;
    assert.ok(app.includes(cle), `clé ${cle} manquante`);
  }
});

// --- rendu : état vert/rouge/gris + libellé ------------------------------

test('AgentFeedsLine rend un point de couleur par état (ok=vert, erreur=rouge, inconnu=gris)', () => {
  assert.match(app, /FLUX_ETAT_COULEUR\s*=\s*\{\s*ok:\s*'#3ecf6a',\s*erreur:\s*'#e5484d',\s*inconnu:\s*'var\(--fg-3\)'\s*\}/);
});

test('AgentFeedsLine affiche titre (ou URL), catégorie et origine pour chaque flux', () => {
  const { corps } = extraireFonction(app, 'AgentFeedsLine');
  assert.match(corps, /f\.title\s*\|\|\s*f\.url/);
  assert.match(corps, /f\.category/);
  assert.match(corps, /f\.origine/);
});
