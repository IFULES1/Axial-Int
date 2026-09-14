// La veille de version : un onglet dont le bundle est plus ancien que le
// serveur doit le savoir (cause des menus « inopérants » du 13/09).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { versionDifferente, creerVeilleVersion, lireVersionServie } from '../app/_prototype/version.js';

test('versionDifferente : vide = jamais, égal = non, différent = oui', () => {
  assert.equal(versionDifferente('', 'abc'), false);
  assert.equal(versionDifferente('abc', ''), false);
  assert.equal(versionDifferente(undefined, undefined), false);
  assert.equal(versionDifferente('abc', 'abc'), false);
  assert.equal(versionDifferente('abc', 'def'), true);
});

function fausseFenetre() {
  const ecouteurs = {};
  let tick = null;
  const doc = {
    visibilityState: 'visible',
    addEventListener: (n, f) => { ecouteurs[n] = f; },
    removeEventListener: (n) => { delete ecouteurs[n]; },
  };
  return {
    document: doc, ecouteurs,
    setInterval: (f) => { tick = f; return 1; },
    clearInterval: () => { tick = null; },
    tic: () => tick && tick(),
    intervalleActif: () => tick !== null,
  };
}
const suivant = () => new Promise((r) => setTimeout(r, 0));

test('signale une fois, puis se démonte (intervalle et écouteur)', async () => {
  const f = fausseFenetre();
  let distante = 'v1';
  const appels = [];
  creerVeilleVersion({ locale: 'v1', lire: async () => distante,
                       onNouvelle: (d) => appels.push(d), fenetre: f });
  await suivant();
  assert.deepEqual(appels, []);
  distante = 'v2';
  f.tic(); await suivant();
  assert.deepEqual(appels, ['v2']);
  assert.equal(f.intervalleActif(), false);
  assert.equal('visibilitychange' in f.ecouteurs, false);
  f.tic(); await suivant();
  assert.deepEqual(appels, ['v2'], 'jamais deux bandeaux');
});

test('vérifie au retour de l onglet au premier plan', async () => {
  const f = fausseFenetre();
  let distante = 'v1';
  const appels = [];
  creerVeilleVersion({ locale: 'v1', lire: async () => distante,
                       onNouvelle: (d) => appels.push(d), fenetre: f });
  await suivant();
  distante = 'v3';
  f.ecouteurs.visibilitychange(); await suivant();
  assert.deepEqual(appels, ['v3']);
});

test('une lecture en échec est ignorée', async () => {
  const f = fausseFenetre();
  const appels = [];
  creerVeilleVersion({ locale: 'v1', lire: async () => { throw new Error('réseau'); },
                       onNouvelle: (d) => appels.push(d), fenetre: f });
  await suivant(); f.tic(); await suivant();
  assert.deepEqual(appels, []);
  assert.equal(f.intervalleActif(), true, 'la veille continue');
});

test('la fonction d arrêt démonte tout', () => {
  const f = fausseFenetre();
  const arreter = creerVeilleVersion({ locale: 'v1', lire: async () => 'v1',
                                       onNouvelle: () => {}, fenetre: f });
  arreter();
  assert.equal(f.intervalleActif(), false);
});

test('lireVersionServie lit `build` de GET /version', async () => {
  const fetchImpl = async (url) => {
    assert.equal(url, '/version');
    return { ok: true, json: async () => ({ build: 'k9-abc' }) };
  };
  assert.equal(await lireVersionServie(fetchImpl), 'k9-abc');
  await assert.rejects(lireVersionServie(async () => ({ ok: false, status: 502 })));
});
