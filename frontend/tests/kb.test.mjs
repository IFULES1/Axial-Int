// Sources v2, Task 6 (spec §5) : écran admin de la base de connaissance Axial
// dans Pilotage. Décision de visibilité du 14/09 (déjà verrouillée par
// `imports.test.mjs` : « mapCitations ne donne aucune étiquette dédiée à
// source==='kb' ») — la base de connaissance ne doit JAMAIS être nommée
// côté utilisateur, seule la surface Pilotage (admin) la montre et la gère.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(racine, 'app/_prototype/App.jsx'), 'utf8');
const bridge = readFileSync(join(racine, 'app/_prototype/bridge.js'), 'utf8');
const pagePartage = readFileSync(join(racine, 'app/p/[pseudo]/[slug]/page.tsx'), 'utf8');

/* Extrait le corps d'une fonction top-level `function nom(...) { … }` par
 * comptage d'accolades (les fonctions imbriquées de PilotageSurface ne
 * doivent pas faire sortir l'extraction trop tôt). */
function extraireFonction(source, nom) {
  const debut = source.indexOf(`function ${nom}(`);
  assert.ok(debut >= 0, `function ${nom} introuvable dans le source`);
  const ouvre = source.indexOf('{', debut);
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

/* Extrait `STRINGS.fr` / `STRINGS.en` par comptage d'accolades, à partir du
 * marqueur `<lang>: {`. */
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

const pilotage = extraireFonction(app, 'PilotageSurface');

test('bridge.js : axKbLister → GET /admin/kb', () => {
  assert.match(bridge, /export\s+async\s+function\s+axKbLister\s*\(\s*\)\s*\{\s*return\s+axFetch\(\s*["']\/admin\/kb["']/);
});

test('bridge.js : axKbAjouterFichier → multipart POST /admin/kb/fichiers', () => {
  const m = bridge.match(/export\s+async\s+function\s+axKbAjouterFichier\s*\([^)]*\)\s*\{[\s\S]*?\n\}/);
  assert.ok(m, 'axKbAjouterFichier introuvable dans bridge.js');
  const corps = m[0];
  assert.match(corps, /\/admin\/kb\/fichiers/);
  assert.match(corps, /FormData/);
  assert.match(corps, /method:\s*["']POST["']/);
});

test('bridge.js : axKbAjouterUrl → POST /admin/kb/urls', () => {
  const m = bridge.match(/export\s+async\s+function\s+axKbAjouterUrl\s*\([^)]*\)\s*\{[\s\S]*?\n\}/);
  assert.ok(m, 'axKbAjouterUrl introuvable dans bridge.js');
  const corps = m[0];
  assert.match(corps, /\/admin\/kb\/urls/);
  assert.match(corps, /method:\s*["']POST["']/);
});

test("bridge.js : axKbSupprimer → DELETE /admin/kb/${encodeURIComponent(docId)}", () => {
  const m = bridge.match(/export\s+async\s+function\s+axKbSupprimer\s*\([^)]*\)\s*\{[\s\S]*?\n\}/);
  assert.ok(m, 'axKbSupprimer introuvable dans bridge.js');
  const corps = m[0];
  // Chaîne précise, pas un motif générique sur l'interpolation (revue Task 6,
  // tour 1, Q1) : la revue a montré qu'un motif générique laisse passer un
  // identifiant faux (doc.id au lieu de doc.doc_id) sans faire échouer le test.
  assert.match(corps, /`\/admin\/kb\/\$\{encodeURIComponent\(docId\)\}`/,
    'axKbSupprimer doit construire exactement `/admin/kb/${encodeURIComponent(docId)}`');
  assert.match(corps, /method:\s*["']DELETE["']/);
});

test('bridge.js : axKbAjouterFichier pose le jeton sur le multipart, sans forcer Content-Type', () => {
  const m = bridge.match(/export\s+async\s+function\s+axKbAjouterFichier\s*\([^)]*\)\s*\{[\s\S]*?\n\}/);
  assert.ok(m, 'axKbAjouterFichier introuvable dans bridge.js');
  const corps = m[0];
  // Le jeton doit être posé (même mécanique qu'axUploadDocument) : sans lui,
  // le premier essai échouerait toujours en 401/403 avant même le refresh.
  assert.match(corps, /Authorization:\s*["']Bearer\s*["']\s*\+\s*tok/,
    "le jeton d'authentification doit être posé sur la requête multipart");
  // `Content-Type` ne doit JAMAIS être fixé à la main sur un envoi FormData :
  // le navigateur doit écrire lui-même la frontière multipart, sinon le
  // backend ne peut plus parser le corps.
  assert.doesNotMatch(corps, /["']Content-Type["']/,
    "axKbAjouterFichier ne doit pas fixer Content-Type sur l'envoi multipart");
});

test('les 4 fonctions KB sont exportées de bridge.js', () => {
  for (const nom of ['axKbLister', 'axKbAjouterFichier', 'axKbAjouterUrl', 'axKbSupprimer']) {
    assert.match(bridge, new RegExp(`export\\s+async\\s+function\\s+${nom}\\b`), `${nom} doit être exporté`);
  }
});

test('PilotageSurface importe les 4 fonctions KB depuis ./bridge', () => {
  const m = app.match(/import\s*\{([^{}]*?)\}\s*from\s*["']\.\/bridge["']/);
  assert.ok(m, "App.jsx doit importer depuis './bridge'");
  const importes = new Set(m[1].split(',').map((s) => s.trim()));
  for (const nom of ['axKbLister', 'axKbAjouterFichier', 'axKbAjouterUrl', 'axKbSupprimer']) {
    assert.ok(importes.has(nom), `${nom} doit être importé d'App.jsx`);
  }
});

test('PilotageSurface appelle bien les 4 fonctions KB (pas un autre écran)', () => {
  for (const nom of ['axKbLister', 'axKbAjouterFichier', 'axKbAjouterUrl', 'axKbSupprimer']) {
    assert.match(pilotage.corps, new RegExp(`\\b${nom}\\s*\\(`), `PilotageSurface doit appeler ${nom}(…)`);
  }
});

test("la suppression envoie doc.doc_id (identifiant Qdrant), pas doc.id (PK de la table)", () => {
  // Revue Task 6, tour 1, C1 : `id` est la clé primaire de `kb_documents`,
  // `doc_id` est l'identifiant Qdrant que la route DELETE attend
  // (`service.supprimer` cherche une ligne par `doc_id`, pas par `id`) —
  // envoyer `doc.id` fait échouer la suppression à 100 % des cas.
  assert.match(pilotage.corps, /\baxKbSupprimer\s*\(\s*doc\.doc_id\s*\)/,
    'axKbSupprimer doit être appelé avec doc.doc_id, pas doc.id');
  assert.doesNotMatch(pilotage.corps, /\baxKbSupprimer\s*\(\s*doc\.id\s*\)/,
    'axKbSupprimer ne doit jamais être appelé avec doc.id (mauvais identifiant)');
});

test('kbLoad et kbSupprimer passent par decrireErreur, comme les deux ajouts (revue, C2)', () => {
  // Les 4 chemins KB de PilotageSurface doivent produire un message localisé
  // (titre/detail via t()), pas le `.message` brut du backend (souvent en
  // français uniquement, sans titre ni action).
  const occurrences = (pilotage.corps.match(/decrireErreur\s*\(/g) || []).length;
  assert.ok(occurrences >= 4,
    `decrireErreur doit être utilisé sur les 4 chemins KB (ajout fichier, ajout URL, listage, suppression) — trouvé ${occurrences} appel(s)`);
});

test("les clés d'i18n kb.* existent en FR et en EN, avec le même ensemble", () => {
  const fr = clesDuDict(extraireDict(app, 'fr'));
  const en = clesDuDict(extraireDict(app, 'en'));
  const clesKbFr = [...fr].filter((k) => k.startsWith('kb.')).sort();
  const clesKbEn = [...en].filter((k) => k.startsWith('kb.')).sort();
  assert.ok(clesKbFr.length > 0, 'aucune clé kb.* trouvée en FR');
  assert.deepEqual(clesKbFr, clesKbEn,
    'les clés kb.* doivent être strictement identiques entre FR et EN');
});

test("aucune mention de la base de connaissance en dehors de PilotageSurface (hors i18n et commentaires)", () => {
  const motif = /base de connaissance|knowledge base/i;
  // Le corps de PilotageSurface est autorisé à en parler (c'est l'écran admin).
  let reste = app.slice(0, pilotage.debut) + app.slice(pilotage.fin);
  // Les valeurs des clés d'i18n `kb.*` / `err.kb_*` (dictionnaires FR/EN) ne
  // comptent pas : ce sont des données, affichées seulement quand
  // PilotageSurface les lit (ou, pour err.kb_*, quand decrireErreur() est
  // appelé depuis PilotageSurface — jamais ailleurs).
  reste = reste.replace(/^\s*'[\w.]*\bkb[\w.]*':.*$/gm, '');
  // Les commentaires (bloc et ligne) sont tolérés (brief : « tolère les
  // commentaires »).
  reste = reste.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
  assert.doesNotMatch(reste, motif,
    'la base de connaissance ne doit apparaître nulle part hors de PilotageSurface (décision de visibilité du 14/09)');
});

test("bridge.js : aucune mention de la base de connaissance hors des commentaires", () => {
  // Revue Task 6, tour 1 (non bloquant) : bridge.js et page.tsx n'ont pas de
  // dictionnaire i18n — aucune exemption `kb.*` à faire ici, seuls les
  // commentaires sont tolérés (bridge.js:574 porte le nom en commentaire de
  // section, ce qui est attendu et sans conséquence pour un utilisateur).
  const motif = /base de connaissance|knowledge base/i;
  const sansCommentaires = bridge.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
  assert.doesNotMatch(sansCommentaires, motif,
    'bridge.js ne doit jamais nommer la base de connaissance en dehors d’un commentaire');
});

test("page.tsx (partage public) : aucune mention de la base de connaissance, même en commentaire", () => {
  // Cette page est publique (visiteurs sans compte) : aucune tolérance, même
  // pour un commentaire — zéro occurrence attendue, comme le constate la revue.
  const motif = /base de connaissance|knowledge base/i;
  assert.doesNotMatch(pagePartage, motif,
    'la page de partage publique ne doit jamais nommer la base de connaissance');
});
