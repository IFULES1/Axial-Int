// Sources v2, Task 7 (spec §6) : Google Drive comme source de documents —
// bouton « Importer depuis Drive » dans la surface Mémoire (DocumentsPanel),
// gating sur `google.selecteur` + les deux variables navigateur du Picker.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(racine, 'app/_prototype/App.jsx'), 'utf8');
const bridge = readFileSync(join(racine, 'app/_prototype/bridge.js'), 'utf8');

/* Extrait le corps d'une fonction top-level `function nom(...) { … }` par
 * comptage d'accolades (même logique que kb.test.mjs). */
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

const documentsPanel = extraireFonction(app, 'DocumentsPanel');

// --- bridge.js ---------------------------------------------------------

test("bridge.js : axImporterDepuisDrive → POST /integrations/google/importer", () => {
  const m = bridge.match(/export\s+async\s+function\s+axImporterDepuisDrive\s*\([^)]*\)\s*\{[\s\S]*?\n\}/);
  assert.ok(m, 'axImporterDepuisDrive introuvable dans bridge.js');
  const corps = m[0];
  assert.match(corps, /\/integrations\/google\/importer/);
  assert.match(corps, /method:\s*["']POST["']/);
  assert.match(corps, /file_id/);
  assert.match(corps, /mime_type/);
});

test('App.jsx importe axImporterDepuisDrive depuis ./bridge', () => {
  const m = app.match(/import\s*\{([^{}]*?)\}\s*from\s*["']\.\/bridge["']/);
  assert.ok(m, "App.jsx doit importer depuis './bridge'");
  const importes = new Set(m[1].split(',').map((s) => s.trim()));
  assert.ok(importes.has('axImporterDepuisDrive'), 'axImporterDepuisDrive doit être importé du bridge');
});

// --- gating du bouton ----------------------------------------------------

test('DocumentsPanel appelle axIntegrations() pour connaître google.selecteur', () => {
  assert.match(documentsPanel.corps, /axIntegrations\s*\(\s*\)/);
});

test('le bouton Drive est conditionné à selecteur ET aux deux variables NEXT_PUBLIC_GOOGLE_*', () => {
  assert.match(documentsPanel.corps, /driveGoogle\.selecteur/,
    'la visibilité doit dépendre de google.selecteur (exposé par GET /integrations/status)');
  assert.match(documentsPanel.corps, /process\.env\.NEXT_PUBLIC_GOOGLE_API_KEY/,
    'NEXT_PUBLIC_GOOGLE_API_KEY doit conditionner le bouton');
  assert.match(documentsPanel.corps, /process\.env\.NEXT_PUBLIC_GOOGLE_CLIENT_ID/,
    'NEXT_PUBLIC_GOOGLE_CLIENT_ID doit conditionner le bouton');
  // Les trois conditions doivent se combiner (ET), pas juste apparaître
  // isolément quelque part dans le composant.
  assert.match(documentsPanel.corps,
    /driveVisible\s*=\s*!!\(\s*driveGoogle\.selecteur\s*&&\s*googleApiKey\s*&&\s*googleClientId\s*\)/,
    'driveVisible doit combiner selecteur && apiKey && clientId');
});

test("si Google n'est pas connecté, le bouton déclenche la connexion (même parcours que Connexions)", () => {
  assert.match(documentsPanel.corps, /driveGoogle\.connecte/);
  assert.match(documentsPanel.corps, /axConnectIntegration\s*\(\s*['"]google['"]\s*\)/);
});

test('un fichier choisi est importé via axImporterDepuisDrive, puis la liste est rechargée', () => {
  assert.match(documentsPanel.corps, /axImporterDepuisDrive\s*\(/);
  assert.match(documentsPanel.corps, /ouvrirPickerDrive\s*\(/);
});

test('les erreurs du chemin Drive passent par decrireErreur (titres/détails localisés)', () => {
  const zoneImport = documentsPanel.corps.slice(
    documentsPanel.corps.indexOf('importerDepuisDrive'));
  assert.match(zoneImport, /decrireErreur\s*\(/);
});

// --- Google Picker : chargement à la demande, une seule fois -------------

test('chargerGooglePicker mémorise sa promesse (chargement une seule fois)', () => {
  assert.match(app, /_googlePickerChargement/);
  assert.match(app, /apis\.google\.com\/js\/api\.js/);
  assert.match(app, /accounts\.google\.com\/gsi\/client/);
});

test('ouvrirPickerDrive construit un DocsView avec setIncludeFolders(false) et setMimeTypes', () => {
  const fn = extraireFonction(app, 'ouvrirPickerDrive');
  assert.match(fn.corps, /google\.picker\.DocsView/);
  assert.match(fn.corps, /setIncludeFolders\s*\(\s*false\s*\)/);
  assert.match(fn.corps, /setMimeTypes\s*\(/);
  assert.match(fn.corps, /setOAuthToken\s*\(/);
  assert.match(fn.corps, /setDeveloperKey\s*\(/);
  assert.match(fn.corps, /setAppId\s*\(/);
});

// --- i18n : parité FR/EN ---------------------------------------------------

test("les clés d'i18n drive.* existent en FR et en EN, avec le même ensemble", () => {
  const fr = clesDuDict(extraireDict(app, 'fr'));
  const en = clesDuDict(extraireDict(app, 'en'));
  const clesDriveFr = [...fr].filter((k) => k.startsWith('drive.')).sort();
  const clesDriveEn = [...en].filter((k) => k.startsWith('drive.')).sort();
  assert.ok(clesDriveFr.length > 0, 'aucune clé drive.* trouvée en FR');
  assert.deepEqual(clesDriveFr, clesDriveEn,
    'les clés drive.* doivent être strictement identiques entre FR et EN');
});

test("les clés d'erreur err.drive_non_connecte et err.drive_inaccessible existent en FR et en EN", () => {
  const fr = clesDuDict(extraireDict(app, 'fr'));
  const en = clesDuDict(extraireDict(app, 'en'));
  for (const base of ['err.drive_non_connecte', 'err.drive_inaccessible']) {
    for (const suffixe of ['.titre', '.detail']) {
      assert.ok(fr.has(base + suffixe), `${base}${suffixe} manquant en FR`);
      assert.ok(en.has(base + suffixe), `${base}${suffixe} manquant en EN`);
    }
  }
});

test('decrireErreur nomme google_non_connecte et drive_fichier_inaccessible', () => {
  assert.match(app, /google_non_connecte:\s*\[\s*['"]err\.drive_non_connecte['"]/);
  assert.match(app, /drive_fichier_inaccessible:\s*\[\s*['"]err\.drive_inaccessible['"]/);
});

// --- .env.local.example ----------------------------------------------------

test('.env.local.example documente les deux variables Google sans y mettre de valeur', () => {
  const exemple = readFileSync(join(racine, '.env.local.example'), 'utf8');
  assert.match(exemple, /^NEXT_PUBLIC_GOOGLE_API_KEY=\s*$/m,
    'NEXT_PUBLIC_GOOGLE_API_KEY doit être documentée, sans valeur');
  assert.match(exemple, /^NEXT_PUBLIC_GOOGLE_CLIENT_ID=\s*$/m,
    'NEXT_PUBLIC_GOOGLE_CLIENT_ID doit être documentée, sans valeur');
});
