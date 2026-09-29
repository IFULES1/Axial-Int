/* Mesure d'audience avec consentement (18/09).
 *
 * Module pur, testé sous Node : décisions de consentement, choix des routes
 * où Clarity a le droit de tourner, construction des événements. Les
 * scripts tiers ne se chargent QUE si l'utilisateur a accepté ET si un
 * identifiant est fourni par l'environnement (sinon rien n'est injecté,
 * aucune requête ne part). Clarity enregistre les écrans : il n'est autorisé
 * que sur la landing, la connexion et l'onboarding, jamais dans l'app
 * (conversations et rapports contiennent des données confidentielles). */

export const CONSENTEMENT_CLE = 'axial_consentement_mesure';
export const CONSENTEMENT_VERSION = '2026-09';
export const ROUTES_CLARITY = ['landing', 'auth', 'reset', 'onb1', 'onb2', 'onb3', 'onb4', 'carte'];

/** 'accepte' | 'refuse' | null (jamais répondu, ou version du bandeau changée). */
export function lireConsentement(stockage = globalThis.localStorage) {
  try {
    const brut = stockage && stockage.getItem(CONSENTEMENT_CLE);
    if (!brut) return null;
    const v = JSON.parse(brut);
    if (!v || v.version !== CONSENTEMENT_VERSION) return null;
    return v.choix === 'accepte' ? 'accepte' : 'refuse';
  } catch (e) { return null; }
}

export function enregistrerConsentement(choix, stockage = globalThis.localStorage) {
  try {
    stockage.setItem(CONSENTEMENT_CLE, JSON.stringify({ choix, version: CONSENTEMENT_VERSION, le: new Date().toISOString() }));
  } catch (e) { /* stockage indisponible : le bandeau reviendra */ }
}

export function clarityAutoriseSur(route) {
  return ROUTES_CLARITY.includes(route);
}

/** Identifiants fournis par l'environnement à la compilation.
 *
 * Next.js ne substitue `process.env.NEXT_PUBLIC_*` dans le bundle navigateur
 * que lorsque l'expression est écrite LITTÉRALEMENT : `env.NEXT_PUBLIC_GA_ID`
 * à travers une variable reste `undefined` côté client (constaté le 29/09,
 * bandeau jamais affiché). Le paramètre `env` ne sert qu'aux tests. */
export function identifiants(env) {
  const ga = env ? env.NEXT_PUBLIC_GA_ID : process.env.NEXT_PUBLIC_GA_ID;
  const clarity = env ? env.NEXT_PUBLIC_CLARITY_ID : process.env.NEXT_PUBLIC_CLARITY_ID;
  return {
    ga: (ga || '').trim() || null,
    clarity: (clarity || '').trim() || null,
  };
}

const _charges = { ga: false, clarity: false };

/** Injecte GA4 (gtag) une seule fois. `doc` injectable pour les tests. */
export function chargerGA(id, doc = globalThis.document) {
  if (!id || _charges.ga || !doc) return false;
  _charges.ga = true;
  const s = doc.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
  doc.head.appendChild(s);
  const w = doc.defaultView || globalThis;
  w.dataLayer = w.dataLayer || [];
  w.gtag = function () { w.dataLayer.push(arguments); };
  // Mode consentement Google (v2) : le script n'est injecté qu'après accord,
  // mais GA4 doit aussi l'entendre explicitement — mesure d'audience
  // accordée, tout ce qui touche à la publicité refusé.
  w.gtag('consent', 'default', {
    analytics_storage: 'granted', ad_storage: 'denied',
    ad_user_data: 'denied', ad_personalization: 'denied',
  });
  w.gtag('js', new Date());
  // Pas d'identifiant publicitaire, IP anonymisée : le strict nécessaire.
  w.gtag('config', id, { anonymize_ip: true, allow_google_signals: false, allow_ad_personalization_signals: false });
  return true;
}

/** Injecte Clarity une seule fois, avec masquage des saisies. */
export function chargerClarity(id, doc = globalThis.document) {
  if (!id || _charges.clarity || !doc) return false;
  _charges.clarity = true;
  const w = doc.defaultView || globalThis;
  w.clarity = w.clarity || function () { (w.clarity.q = w.clarity.q || []).push(arguments); };
  const s = doc.createElement('script');
  s.async = true;
  s.src = `https://www.clarity.ms/tag/${encodeURIComponent(id)}`;
  doc.head.appendChild(s);
  return true;
}

/* Une fois injecté sur la landing, le script Clarity survit à la navigation
 * interne vers l'app (même page, même session) : sans ces deux appels, il
 * continuerait d'enregistrer les conversations et les rapports. `stop` et
 * `start` sont l'API officielle de Clarity. */
let _clarityActif = true;
export function suspendreClarity(w = globalThis) {
  if (!_charges.clarity || typeof w.clarity !== 'function' || !_clarityActif) return false;
  w.clarity('stop');
  _clarityActif = false;
  return true;
}
export function reprendreClarity(w = globalThis) {
  if (!_charges.clarity || typeof w.clarity !== 'function' || _clarityActif) return false;
  w.clarity('start');
  _clarityActif = true;
  return true;
}
export function clarityActif() { return _charges.clarity && _clarityActif; }

/** Envoie un événement produit à GA4 s'il est chargé ; sinon ne fait rien. */
export function evenement(nom, proprietes = {}, w = globalThis) {
  if (!w || typeof w.gtag !== 'function') return false;
  w.gtag('event', nom, proprietes);
  return true;
}

export function _reinitialiserPourTests() { _charges.ga = false; _charges.clarity = false; _clarityActif = true; }
