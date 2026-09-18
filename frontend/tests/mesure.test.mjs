import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  lireConsentement, enregistrerConsentement, clarityAutoriseSur, identifiants,
  chargerGA, chargerClarity, evenement, _reinitialiserPourTests, CONSENTEMENT_VERSION,
} from '../app/_prototype/mesure.js';

const memoire = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) }; };
const fauxDoc = () => { const head = { enfants: [], appendChild(e) { this.enfants.push(e); } }; const w = {}; return { head, createElement: () => ({}), defaultView: w, w }; };

test('consentement : rien, puis accepté, puis version changée', () => {
  const s = memoire();
  assert.equal(lireConsentement(s), null);
  enregistrerConsentement('accepte', s);
  assert.equal(lireConsentement(s), 'accepte');
  s.setItem('axial_consentement_mesure', JSON.stringify({ choix: 'accepte', version: 'ancienne' }));
  assert.equal(lireConsentement(s), null, 'un bandeau modifié redemande');
  enregistrerConsentement('refuse', s);
  assert.equal(lireConsentement(s), 'refuse');
  assert.equal(CONSENTEMENT_VERSION, '2026-09');
});

test('Clarity : landing, auth et onboarding seulement', () => {
  for (const r of ['landing', 'auth', 'onb1', 'onb4', 'carte']) assert.ok(clarityAutoriseSur(r), r);
  assert.equal(clarityAutoriseSur('app'), false);
});

test('identifiants vides = rien ne se charge', () => {
  _reinitialiserPourTests();
  assert.deepEqual(identifiants({}), { ga: null, clarity: null });
  const d = fauxDoc();
  assert.equal(chargerGA(null, d), false);
  assert.equal(chargerClarity('', d), false);
  assert.equal(d.head.enfants.length, 0);
});

test('GA4 chargé une seule fois, IP anonymisée, événements transmis', () => {
  _reinitialiserPourTests();
  const d = fauxDoc();
  assert.equal(chargerGA('G-TEST1234', d), true);
  assert.equal(chargerGA('G-TEST1234', d), false, 'pas deux fois');
  assert.equal(d.head.enfants.length, 1);
  assert.match(d.head.enfants[0].src, /gtag\/js\?id=G-TEST1234/);
  const config = d.w.dataLayer.find((a) => a[0] === 'config');
  assert.equal(config[2].anonymize_ip, true);
  assert.equal(evenement('inscription', { source: 'test' }, d.w), true);
  assert.ok(d.w.dataLayer.some((a) => a[0] === 'event' && a[1] === 'inscription'));
  assert.equal(evenement('x', {}, {}), false, 'sans gtag, rien');
});

test('Clarity chargé une seule fois', () => {
  _reinitialiserPourTests();
  const d = fauxDoc();
  assert.equal(chargerClarity('abc123', d), true);
  assert.equal(chargerClarity('abc123', d), false);
  assert.match(d.head.enfants[0].src, /clarity\.ms\/tag\/abc123/);
});

test('App.jsx : bandeau de consentement sur toutes les sorties, événements posés', () => {
  const app = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', 'app/_prototype/App.jsx'), 'utf8');
  assert.match(app, /import \{[^}]*lireConsentement[^}]*\} from "\.\/mesure"/);
  assert.match(app, /\{bandeauConsentement\}/);
  for (const e of ["evenement\\('inscription'", "evenement\\('rapport_lance'", "evenement\\('conversation_envoyee'"]) assert.match(app, new RegExp(e), e);
  assert.match(app, /clarityAutoriseSur\(route\)/);
  for (const cle of ["'mesure.titre'", "'mesure.accepter'", "'mesure.refuser'"]) assert.equal((app.match(new RegExp(cle + ': ', 'g')) || []).length, 2, cle + ' FR+EN');
});
