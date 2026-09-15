// Sources v2, Task 7 (spec §6) : Google Drive comme source de documents —
// bouton « Importer depuis Drive » dans la surface Mémoire (DocumentsPanel),
// gating sur `google.selecteur` + les deux variables navigateur du Picker.
//
// Tour de correction 1 (revue task-7-review.md) : `chargerGooglePicker` /
// `obtenirJetonPickerDrive` / `ouvrirPickerDrive` sont sortis d'App.jsx vers
// un module pur `app/_prototype/drive.js`, importé ici pour de vrai (comme
// `version.test.mjs` importe `version.js`) plutôt que relus par expression
// rationnelle — pour exercer la mémorisation réelle, pas seulement sa
// présence textuelle dans le source.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  GOOGLE_PICKER_SCOPE,
  GOOGLE_PICKER_MIME_TYPES,
  chargerGooglePicker,
  obtenirJetonPickerDrive,
  ouvrirPickerDrive,
  _reinitialiserChargementPourTests,
} from '../app/_prototype/drive.js';

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

/* Stubs minimaux de `document`/`window` — pas jsdom, juste ce dont
 * `chargerGooglePicker`/`obtenirJetonPickerDrive`/`ouvrirPickerDrive` ont
 * besoin. Les fonctions de drive.js ne référencent ces globales qu'À
 * L'APPEL (jamais au niveau du module), donc les poser juste avant chaque
 * test suffit — pas besoin de jsdom pour ce module. */
function poserStubsNavigateur({ gapiLoadAppelle, googleAccounts, googlePicker } = {}) {
  const scripts = [];
  global.document = {
    createElement: (tag) => {
      const el = { tagName: tag, _listeners: {} };
      Object.defineProperty(el, 'onload', { set(fn) { el._onload = fn; }, get() { return el._onload; } });
      Object.defineProperty(el, 'onerror', { set(fn) { el._onerror = fn; }, get() { return el._onerror; } });
      scripts.push(el);
      return el;
    },
    head: { appendChild: (el) => { if (el._onload) queueMicrotask(el._onload); } },
  };
  global.window = {
    gapi: { load: (nom, cb) => { if (gapiLoadAppelle) gapiLoadAppelle(nom); cb(); } },
    google: {
      accounts: googleAccounts || { oauth2: { initTokenClient: () => ({ requestAccessToken() {} }) } },
      picker: googlePicker,
    },
  };
  return scripts;
}

// --- drive.js : chargement des scripts, mémorisation ------------------

test('chargerGooglePicker mémorise sa promesse : deux appels renvoient la même promesse, un seul jeu de scripts injecté', () => {
  _reinitialiserChargementPourTests();
  const scripts = poserStubsNavigateur();

  const p1 = chargerGooglePicker();
  const p2 = chargerGooglePicker();

  assert.strictEqual(p1, p2, 'les deux appels doivent renvoyer EXACTEMENT la même promesse (mémorisation)');
  // Exactement 2 balises <script> au total (api.js + gsi/client), jamais 4 :
  // supprimer le garde `if (_googlePickerChargement) return …` laisserait ce
  // compte passer à 4 et ferait échouer cette assertion (revue Task 7, tour
  // 1, bloquant qualité 3 : l'ancien test ne le vérifiait pas réellement).
  assert.strictEqual(scripts.length, 2, `2 scripts attendus (api.js + gsi/client), ${scripts.length} injecté(s)`);
});

test('chargerGooglePicker : un échec de chargement remet le cache à zéro (un essai suivant relance)', async () => {
  _reinitialiserChargementPourTests();
  global.document = {
    createElement: () => {
      const el = {};
      queueMicrotask(() => el.onerror && el.onerror());
      return el;
    },
    head: { appendChild: () => {} },
  };
  global.window = { gapi: { load: () => {} } };

  await assert.rejects(chargerGooglePicker());
  // Après l'échec, un nouvel appel doit retenter (pas de promesse rejetée
  // mémorisée pour toujours).
  const scriptsApres = poserStubsNavigateur();
  const p = chargerGooglePicker();
  await p;
  assert.strictEqual(scriptsApres.length, 2, 'un nouvel essai doit réinjecter les 2 scripts');
});

test('les mimeTypes du Picker couvrent les formats documents.ingest + les 3 types Google natifs', () => {
  const types = GOOGLE_PICKER_MIME_TYPES.split(',');
  for (const attendu of [
    'application/pdf', 'text/csv', 'text/plain',
    'application/vnd.google-apps.document',
    'application/vnd.google-apps.spreadsheet',
    'application/vnd.google-apps.presentation',
  ]) {
    assert.ok(types.includes(attendu), `${attendu} doit figurer dans GOOGLE_PICKER_MIME_TYPES`);
  }
});

test('GOOGLE_PICKER_SCOPE est bien le scope minimal drive.file', () => {
  assert.equal(GOOGLE_PICKER_SCOPE, 'https://www.googleapis.com/auth/drive.file');
});

// --- drive.js : jeton navigateur — succès, refus explicite, error_callback ---

test('obtenirJetonPickerDrive résout avec le access_token du callback', async () => {
  global.window = {
    google: {
      accounts: {
        oauth2: {
          initTokenClient: ({ callback }) => ({
            requestAccessToken: () => callback({ access_token: 'JETON123' }),
          }),
        },
      },
    },
  };
  const jeton = await obtenirJetonPickerDrive('client-id');
  assert.equal(jeton, 'JETON123');
});

test("obtenirJetonPickerDrive rejette avec code 'drive_autorisation_refusee' si le callback ne porte pas de jeton", async () => {
  global.window = {
    google: {
      accounts: {
        oauth2: {
          initTokenClient: ({ callback }) => ({
            requestAccessToken: () => callback({}),
          }),
        },
      },
    },
  };
  await assert.rejects(obtenirJetonPickerDrive('client-id'),
    (e) => e.code === 'drive_autorisation_refusee');
});

test("obtenirJetonPickerDrive expose error_callback : popup bloquée ou fenêtre fermée rejette (ne reste jamais pendante)", async () => {
  // Revue Task 7, tour 1, bloquant qualité 1 : sans `error_callback`, ce
  // scénario (le SEUL chemin réaliste au premier clic si les scripts ne sont
  // pas préchargés) ne réglait jamais la promesse — `driveBusy` restait
  // bloqué indéfiniment côté DocumentsPanel.
  let errorCb;
  global.window = {
    google: {
      accounts: {
        oauth2: {
          initTokenClient: ({ error_callback }) => {
            errorCb = error_callback;
            return { requestAccessToken: () => { /* la popup ne s'ouvre jamais */ } };
          },
        },
      },
    },
  };
  const p = obtenirJetonPickerDrive('client-id');
  assert.equal(typeof errorCb, 'function', 'initTokenClient doit recevoir un error_callback');
  errorCb({ type: 'popup_failed_to_open' });
  await assert.rejects(p, (e) => e.code === 'drive_autorisation_refusee');
});

// --- drive.js : ouvrirPickerDrive construit bien le Picker --------------

test('ouvrirPickerDrive construit un DocsView avec setIncludeFolders(false) et setMimeTypes, puis le PickerBuilder attendu', async () => {
  const appels = [];
  const vueChainable = {
    setIncludeFolders(v) { appels.push(['setIncludeFolders', v]); return this; },
    setMimeTypes(v) { appels.push(['setMimeTypes', v]); return this; },
  };
  function DocsView() { return vueChainable; }
  const builderChainable = {
    addView(v) { appels.push(['addView', v]); return this; },
    setOAuthToken(v) { appels.push(['setOAuthToken', v]); return this; },
    setDeveloperKey(v) { appels.push(['setDeveloperKey', v]); return this; },
    setAppId(v) { appels.push(['setAppId', v]); return this; },
    setCallback(cb) {
      appels.push(['setCallback']);
      queueMicrotask(() => cb({ action: 'picked', docs: [{ id: 'f1', name: 'n1', mimeType: 'application/pdf' }] }));
      return this;
    },
    build() { return { setVisible: () => {} }; },
  };
  function PickerBuilder() { return builderChainable; }

  global.window = {
    google: {
      accounts: {
        oauth2: {
          initTokenClient: ({ callback }) => ({ requestAccessToken: () => callback({ access_token: 'JETON' }) }),
        },
      },
      picker: { DocsView, PickerBuilder, Action: { PICKED: 'picked', CANCEL: 'cancel' } },
    },
  };

  const fichiers = await ouvrirPickerDrive('api-key', '123456-abcdef.apps.googleusercontent.com');
  assert.deepEqual(fichiers, [{ id: 'f1', name: 'n1', mimeType: 'application/pdf' }]);

  const noms = appels.map((a) => a[0]);
  assert.deepEqual(noms, ['setIncludeFolders', 'setMimeTypes', 'addView', 'setOAuthToken', 'setDeveloperKey', 'setAppId', 'setCallback']);
  assert.equal(appels.find((a) => a[0] === 'setIncludeFolders')[1], false);
  assert.equal(appels.find((a) => a[0] === 'setOAuthToken')[1], 'JETON');
  assert.equal(appels.find((a) => a[0] === 'setDeveloperKey')[1], 'api-key');
  assert.equal(appels.find((a) => a[0] === 'setAppId')[1], '123456');
});

test('ouvrirPickerDrive renvoie [] sur CANCEL', async () => {
  global.window = {
    google: {
      accounts: { oauth2: { initTokenClient: ({ callback }) => ({ requestAccessToken: () => callback({ access_token: 'J' }) }) } },
      picker: {
        DocsView: function () { return { setIncludeFolders() { return this; }, setMimeTypes() { return this; } }; },
        PickerBuilder: function () {
          return {
            addView() { return this; }, setOAuthToken() { return this; },
            setDeveloperKey() { return this; }, setAppId() { return this; },
            setCallback(cb) { queueMicrotask(() => cb({ action: 'cancel' })); return this; },
            build() { return { setVisible() {} }; },
          };
        },
        Action: { PICKED: 'picked', CANCEL: 'cancel' },
      },
    },
  };
  const fichiers = await ouvrirPickerDrive('k', '1-x.apps.googleusercontent.com');
  assert.deepEqual(fichiers, []);
});

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

test('App.jsx importe axImporterDepuisDrive depuis ./bridge, et chargerGooglePicker/ouvrirPickerDrive depuis ./drive', () => {
  const mBridge = app.match(/import\s*\{([^{}]*?)\}\s*from\s*["']\.\/bridge["']/);
  assert.ok(mBridge, "App.jsx doit importer depuis './bridge'");
  const importesBridge = new Set(mBridge[1].split(',').map((s) => s.trim()));
  assert.ok(importesBridge.has('axImporterDepuisDrive'), 'axImporterDepuisDrive doit être importé du bridge');

  const mDrive = app.match(/import\s*\{([^{}]*?)\}\s*from\s*["']\.\/drive["']/);
  assert.ok(mDrive, "App.jsx doit importer depuis './drive' (module pur, revue tour 1)");
  const importesDrive = new Set(mDrive[1].split(',').map((s) => s.trim()));
  assert.ok(importesDrive.has('chargerGooglePicker'));
  assert.ok(importesDrive.has('ouvrirPickerDrive'));
});

// --- gating et cycle de vie du bouton (DocumentsPanel) ------------------

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
  assert.match(documentsPanel.corps,
    /driveVisible\s*=\s*!!\(\s*driveGoogle\.selecteur\s*&&\s*googleApiKey\s*&&\s*googleClientId\s*\)/,
    'driveVisible doit combiner selecteur && apiKey && clientId');
});

test('les scripts du Picker sont préchargés au montage (driveVisible), pas au clic', () => {
  // Revue Task 7, tour 1, bloquant qualité 1 : `requestAccessToken()` doit
  // s'exécuter dans le geste utilisateur — un chargement de scripts encore
  // en cours au clic fait perdre ce geste et bloque la popup Google.
  assert.match(documentsPanel.corps,
    /React\.useEffect\s*\(\s*\(\)\s*=>\s*\{\s*if\s*\(\s*driveVisible\s*\)\s*chargerGooglePicker\s*\(\s*\)/,
    "un useEffect doit appeler chargerGooglePicker() dès que driveVisible devient vrai");
});

test("si Google n'est pas connecté, le bouton déclenche la connexion (même parcours que Connexions)", () => {
  assert.match(documentsPanel.corps, /driveGoogle\.connecte/);
  assert.match(documentsPanel.corps, /axConnectIntegration\s*\(\s*['"]google['"]\s*\)/);
});

test('un fichier choisi est importé via axImporterDepuisDrive', () => {
  assert.match(documentsPanel.corps, /axImporterDepuisDrive\s*\(/);
  assert.match(documentsPanel.corps, /ouvrirPickerDrive\s*\(/);
});

test('setDriveBusy(false) est posé dans un finally (jamais bloqué si le jeton échoue)', () => {
  const zone = documentsPanel.corps.slice(documentsPanel.corps.indexOf('importerDepuisDrive'));
  const mFinally = zone.match(/\}\s*finally\s*\{/);
  assert.ok(mFinally, 'importerDepuisDrive doit avoir un bloc finally (code, pas juste le mot en commentaire)');
  const blocFinally = zone.slice(mFinally.index, mFinally.index + 500);
  assert.match(blocFinally, /setDriveBusy\s*\(\s*false\s*\)/,
    'setDriveBusy(false) doit être posé dans le finally, pas seulement en fin de try');
});

test('load() est rappelé dans le finally (un import partiel reste visible)', () => {
  const zone = documentsPanel.corps.slice(documentsPanel.corps.indexOf('importerDepuisDrive'));
  const mFinally = zone.match(/\}\s*finally\s*\{/);
  assert.ok(mFinally);
  const blocFinally = zone.slice(mFinally.index, mFinally.index + 500);
  assert.match(blocFinally, /load\s*\(\s*\)/,
    'load() doit être appelé dans le finally, pour rafraîchir même si un import a échoué en cours de boucle');
});

test('les erreurs du chemin Drive passent par decrireErreur (titres/détails localisés)', () => {
  const zoneImport = documentsPanel.corps.slice(documentsPanel.corps.indexOf('importerDepuisDrive'));
  assert.match(zoneImport, /decrireErreur\s*\(/);
});

// --- decrireErreur : codes nommés ---------------------------------------

test('decrireErreur nomme google_non_connecte, drive_fichier_inaccessible et drive_autorisation_refusee', () => {
  assert.match(app, /google_non_connecte:\s*\[\s*['"]err\.drive_non_connecte['"]/);
  assert.match(app, /drive_fichier_inaccessible:\s*\[\s*['"]err\.drive_inaccessible['"]/);
  assert.match(app, /drive_autorisation_refusee:\s*\[\s*['"]err\.drive_autorisation_refusee['"]/);
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

test("les clés d'erreur err.drive_non_connecte, err.drive_inaccessible et err.drive_autorisation_refusee existent en FR et en EN", () => {
  const fr = clesDuDict(extraireDict(app, 'fr'));
  const en = clesDuDict(extraireDict(app, 'en'));
  for (const base of ['err.drive_non_connecte', 'err.drive_inaccessible', 'err.drive_autorisation_refusee']) {
    for (const suffixe of ['.titre', '.detail']) {
      assert.ok(fr.has(base + suffixe), `${base}${suffixe} manquant en FR`);
      assert.ok(en.has(base + suffixe), `${base}${suffixe} manquant en EN`);
    }
  }
});

test('err.drive_inaccessible mentionne, en FR et en EN, de vérifier le compte Google connecté', () => {
  const fr = extraireDict(app, 'fr');
  const en = extraireDict(app, 'en');
  const mFr = fr.match(/'err\.drive_inaccessible\.detail':\s*"([^"]*)"/);
  const mEn = en.match(/'err\.drive_inaccessible\.detail':\s*'([^']*)'/);
  assert.ok(mFr, 'err.drive_inaccessible.detail FR introuvable');
  assert.ok(mEn, 'err.drive_inaccessible.detail EN introuvable');
  assert.match(mFr[1], /compte Google/);
  assert.match(mEn[1], /Google account/);
});

// --- frontend/README.md -----------------------------------------------

test('frontend/README.md documente les deux variables Google dans une section « Variables d\'environnement »', () => {
  const readme = readFileSync(join(racine, 'README.md'), 'utf8');
  assert.match(readme, /Variables d'environnement/);
  assert.match(readme, /NEXT_PUBLIC_GOOGLE_API_KEY/);
  assert.match(readme, /NEXT_PUBLIC_GOOGLE_CLIENT_ID/);
});

test("frontend/.env.local.example n'existe plus (gitignoré, disparaissait au clone — revue tour 1)", () => {
  assert.throws(() => readFileSync(join(racine, '.env.local.example'), 'utf8'));
});
