/* Task 5 — liste, gestion, comparaison, export, partage, page publique.
 *
 * Deux natures de test ici, assumées :
 *  - de vrais tests unitaires sur les modules PURS (`jeton.js`,
 *    `rapports_etat.js`) — le jeton de partage et la date de fin du
 *    chronomètre sont les deux endroits où une erreur passerait inaperçue ;
 *  - des tests de CÂBLAGE (lecture de `App.jsx`, `bridge.js`, `globals.css`) :
 *    le prototype n'est pas montable en Node (il touche `window` à
 *    l'importation), et un bouton branché sur une fonction absente ne se voit
 *    ni au `next build` ni à l'œil. Ce sont les mêmes garde-fous que
 *    `etapes.test.mjs` (test 15).
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { jetonDuSlug, LONGUEUR_JETON } from '../app/p/jeton.js';
import { etatDepuisRapport, etatDepuisStockage, versStockage,
         etatDepuisEvenement, etatAuLancement } from '../app/_prototype/rapports_etat.js';

const app = readFileSync(new URL('../app/_prototype/App.jsx', import.meta.url), 'utf8');
const bridge = readFileSync(new URL('../app/_prototype/bridge.js', import.meta.url), 'utf8');
const css = readFileSync(new URL('../app/globals.css', import.meta.url), 'utf8');
const pagePublique = readFileSync(
  new URL('../app/p/[pseudo]/[slug]/page.tsx', import.meta.url), 'utf8');
const cssPartage = readFileSync(new URL('../app/p/partage.css', import.meta.url), 'utf8');
const etatsPartage = readFileSync(new URL('../app/p/etats.tsx', import.meta.url), 'utf8');
const notFoundPartage = readFileSync(
  new URL('../app/p/[pseudo]/[slug]/not-found.tsx', import.meta.url), 'utf8');

/* ---------------------------------------------------------------- */

test('1 — le jeton se lit sur les 22 derniers caractères, tiret compris', () => {
  assert.equal(LONGUEUR_JETON, 22);
  // Cas nominal : slug de titre + tiret + jeton.
  assert.equal(
    jetonDuSlug('marche-du-lithium-en-europe-AbCdEfGhIjKlMnOpQrStUv'),
    'AbCdEfGhIjKlMnOpQrStUv');
  /* LE cas que « après le dernier tiret » cassait : `token_urlsafe` tire dans
     l'alphabet base64url, donc un jeton peut CONTENIR un tiret. Ici le dernier
     tiret de l'URL est à l'intérieur du jeton. */
  const avecTiret = 'AbCdEfGhIjKl-nOpQrStUv';
  assert.equal(avecTiret.length, 22);
  assert.equal(jetonDuSlug('marche-du-lithium-' + avecTiret), avecTiret);
  // Un jeton commençant par un tiret ne perd pas son premier caractère.
  const commenceParTiret = '-bCdEfGhIjKlMnOpQrStUv';
  assert.equal(jetonDuSlug('titre-' + commenceParTiret), commenceParTiret);
  // Titre vide (le serveur pose quand même le tiret séparateur).
  assert.equal(jetonDuSlug('-AbCdEfGhIjKlMnOpQrStUv'), 'AbCdEfGhIjKlMnOpQrStUv');
  // Jeton seul, sans slug devant.
  assert.equal(jetonDuSlug('AbCdEfGhIjKlMnOpQrStUv'), 'AbCdEfGhIjKlMnOpQrStUv');
});

test('2 — un segment qui ne peut pas porter de jeton rend null', () => {
  assert.equal(jetonDuSlug(''), null);
  assert.equal(jetonDuSlug(null), null);
  assert.equal(jetonDuSlug(undefined), null);
  assert.equal(jetonDuSlug('trop-court'), null);
  // 22 caractères, mais pas de tiret séparateur devant : les 22 dernières
  // lettres de n'importe quelle URL ne sont pas un jeton.
  assert.equal(jetonDuSlug('xmarche-du-lithium-AbCdEfGhIjKlMnOpQrStUv'.replace('-Ab', 'zAb')), null);
  // Caractère hors alphabet base64url dans les 22 derniers.
  assert.equal(jetonDuSlug('titre-AbCdEfGhIjKlMnOpQrSt.v'), null);
  assert.equal(jetonDuSlug('titre-AbCdEfGh/jKlMnOpQrStUv'), null);
  // Segment mal encodé : pas d'exception, un `null` ou un jeton, jamais un jet.
  assert.doesNotThrow(() => jetonDuSlug('titre-%E0%A4%A'));
});

/* ---------------------------------------------------------------- */

test('3 — le chronomètre d’un rapport terminé est figé sur `termine_at`', () => {
  const etat = etatDepuisRapport({
    id: 'r1', statut: 'annule', progression: 100,
    created_at: '2026-09-12T17:00:00+00:00',
    termine_at: '2026-09-12T17:04:30+00:00',
  });
  assert.equal(etat.fin, '2026-09-12T17:04:30+00:00');
  // Aller-retour par le stockage : la date de fin survit au rechargement,
  // sinon le compteur repartirait de zéro sur l'écran d'échec.
  const relu = etatDepuisStockage(versStockage(etat));
  assert.equal(relu.fin, '2026-09-12T17:04:30+00:00');
  assert.equal(relu.debut, '2026-09-12T17:00:00+00:00');

  // En cours : aucune date de fin, l'horloge doit courir.
  const enCours = etatDepuisRapport({
    id: 'r2', statut: 'en_cours', progression: 40,
    created_at: '2026-09-12T17:00:00+00:00', termine_at: null,
  });
  assert.equal(enCours.fin, null);

  // Le flux qui rapporte une erreur pose lui-même une date de fin : le `done`
  // d'erreur ne porte pas de `ReportDetail`.
  const echoue = etatDepuisEvenement(etatAuLancement('Question'),
    { done: true, error: 'Le modèle est indisponible.', code: 'llm_unavailable' });
  assert.equal(echoue.statut, 'echec');
  assert.ok(echoue.fin, 'un échec doit porter une date de fin');

  // `delai_depasse` n'est PAS une fin : la tâche tourne encore, le chronomètre
  // doit continuer d'avancer pendant que le polling prend le relais.
  const perdu = etatDepuisEvenement(etatAuLancement('Question'),
    { done: true, error: 'délai', code: 'delai_depasse' });
  assert.equal(perdu.statut, 'en_cours');
  assert.ok(!perdu.fin, 'un suivi abandonné ne fige pas le chronomètre');
});

test('4 — le chronomètre lit `etat.fin` et gèle l’écran terminal', () => {
  // La règle est dans la vue : sur un statut terminal, le temps écoulé se
  // calcule jusqu'à `instantFin`, jamais jusqu'à `Date.now()`.
  assert.match(app, /const instantFin = \(\) => \{|const instantFin = \(\(\) => \{/);
  assert.match(app, /if \(!terminal\) return Date\.now\(\);/);
  assert.match(app, /Math\.floor\(\(instantFin - depart\) \/ 1000\)/);
  assert.ok(!/Math\.floor\(\(Date\.now\(\) - depart\) \/ 1000\)/.test(app),
    'le chronomètre ne doit plus se calculer directement sur Date.now()');
});

/* ---------------------------------------------------------------- */

test('5 — le bridge porte les routes de gestion, de partage et d’export', () => {
  for (const [nom, motif] of [
    ['axRenommerRapport', /patcherRapport\(id, \{ title: titre \}\)/],
    ['axEpinglerRapport', /pinned: !!epingle/],
    ['axArchiverRapport', /archived: !!archive/],
    ['axDeplacerRapport', /project_id: projectId \|\| null/],
    ['axSupprimerRapport', /method: "DELETE"/],
    ['axRechercherRapports', /\/reports\/search\?q=/],
    ['axPartagerRapport', /reports\/\$\{id\}\/partage/],
    ['axRevoquerPartage', /reports\/\$\{id\}\/partage/],
    ['axExporterRapport', /\/export\?format=\$\{fmt\}/],
  ]) {
    assert.match(bridge, new RegExp(`export async function ${nom}\\b`), nom);
    assert.match(bridge, motif, nom + ' — route');
  }
  // `PATCH` et non `PUT` : sémantique PATCH stricte côté serveur.
  assert.match(bridge, /method: "PATCH", body: patch/);
  // L'ancien chemin PDF-seulement a disparu : les trois formats passent par
  // `?format=`, tous partis du même markdown archivé.
  // (Le nom ne subsiste que dans le commentaire qui explique son remplacement.)
  assert.ok(!/export async function axDownloadReportPdf/.test(bridge),
    'axDownloadReportPdf doit avoir disparu du bridge');
  assert.ok(!/axDownloadReportPdf\(/.test(app),
    'axDownloadReportPdf ne doit plus être appelée');
  // Un blob téléchargé se révoque, sinon il reste en mémoire jusqu'au
  // rechargement de la page.
  assert.match(bridge, /axExporterRapport[\s\S]{0,1600}revokeObjectURL/);
});

test('6 — toutes les fonctions ax… appelées par App.jsx sont importées', () => {
  // Même garde-fou que `imports.test.mjs`, rejoué ici sur le lot Task 5 : une
  // fonction appelée mais pas importée ne casse ni le build ni le typage,
  // seulement le clic.
  const m = /import \{([^{}]*?)\} from "\.\/bridge"/.exec(app);
  assert.ok(m, 'import du bridge introuvable');
  const importes = new Set(m[1].split(',').map((s) => s.trim()).filter(Boolean));
  for (const nom of ['axRenommerRapport', 'axEpinglerRapport', 'axArchiverRapport',
                     'axDeplacerRapport', 'axSupprimerRapport', 'axRechercherRapports',
                     'axPartagerRapport', 'axRevoquerPartage', 'axExporterRapport']) {
    assert.ok(importes.has(nom), `${nom} appelé mais non importé`);
  }
});

/* ---------------------------------------------------------------- */

test('7 — la liste réemploie les composants de la liste des conversations', () => {
  assert.match(app, /function ReportsList\(/);
  // Menu ⋯, groupes repliables, surlignage des extraits : les mêmes
  // composants, pas des copies.
  const liste = app.slice(app.indexOf('function ReportsList('),
                          app.indexOf('function ReportsEmpty('));
  assert.ok(liste.length > 1000, 'corps de ReportsList introuvable');
  assert.match(liste, /<MenuConversation/);
  assert.match(liste, /<DossierGroupe/);
  assert.match(liste, /surlignerExtrait\(/);
  // Les cinq entrées du menu + « Comparer avec… ».
  for (const cle of ['conv.menu.renommer', 'conv.menu.epingler', 'conv.menu.archiver',
                     'conv.menu.deplacer', 'common.delete', 'reports.menu.comparer']) {
    assert.ok(app.includes(`'${cle}'`), `entrée de menu absente : ${cle}`);
  }
  // Recherche à partir de 3 caractères, avec débounce.
  assert.match(app, /terme\.length < 3[\s\S]{0,400}axRechercherRapports\(terme\)/);
  // « Charger plus » borné par le curseur `before` du dernier rapport affiché.
  assert.match(app, /chargerPlus: \(\) => \{[\s\S]{0,200}chargerRapports\(\{ before: dernier\.id \}\)/);
  /* Archives demandées SEULEMENT à la première ouverture de la section, et en
     FUSION : ouvrir « Archivés » après trois « Charger plus » ne doit pas jeter
     les pages déjà chargées (revue Task 5, finding 9). */
  assert.match(app, /chargerArchives: \(\) => chargerRapports\(\{ inclureArchives: true, fusionner: true \}\)/);
  assert.match(app, /if \(!before && !fusionner\) return items;/);
  assert.match(app, /if \(ouvrir && !archivesChargees\) gestion\.chargerArchives\(\);/);
});

test('8 — un rapport sans dossier connu est rendu sous « Récents »', () => {
  /* Même règle que les conversations : `project_id` nul OU absent de `projets`
     (liste pas encore revenue) tombe dans le groupe à plat, jamais dans le
     néant. C'est ce qui empêche un rapport de devenir invisible. */
  assert.match(app, /const connus = new Set\(\(projets \|\| \[\]\)\.map\(\(p\) => p\.id\)\);/);
  assert.match(app, /const sansDossier = rapports\.filter\(\s*\n?\s*\(r\) => !r\.archived_at && !r\.pinned_at && !connus\.has\(r\.project_id\)\);/);
  /* Les en-têtes de section suivent les listes FILTRÉES : une recherche sans
     correspondance ne doit pas laisser « ÉPINGLÉS » / « RÉCENTS » au-dessus du
     vide (revue Task 5, finding 7). */
  assert.match(app, /const epinglesVisibles = epingles\.filter\(filtre\);/);
  assert.match(app, /const sansDossierVisibles = sansDossier\.filter\(filtre\);/);
  assert.match(app, /\{epinglesVisibles\.length > 0 &&/);
  assert.match(app, /\{sansDossierVisibles\.length > 0 &&/);
  assert.match(app, /\{t\('reports\.section\.recents'\)\}[\s\S]{0,200}sansDossierVisibles\.map\(ligne\)/);
});

test('9 — la liste est relue au retour sur le composeur', () => {
  // Sans cette relecture, une ligne « en cours » restait affichée après la fin
  // de la génération et le rapport terminé n'apparaissait pas (revue Task 4).
  assert.match(app, /subRoute !== 'reports' \|\| reportsState !== 'empty'\) return;\s*\n\s*chargerRapports\(\{\}\);/);
  // Garde contre un double chargement (double clic, effet rejoué).
  assert.match(app, /if \(rapportsEnVol\.current\) return;/);
});

test('10 — les mutations de liste sont optimistes et réversibles', () => {
  assert.match(app, /const muterRapport = async \(id, patch, appel\)/);
  // L'instantané est pris DANS la mise à jour fonctionnelle : deux clics dans
  // le même tick ne doivent pas restaurer une valeur périmée.
  assert.match(app, /setRapports\(\(rs\) => \{[\s\S]{0,400}retour = \{\};/);
  // Archiver dépingle, comme côté serveur.
  assert.match(app, /archived_at: archive \? maintenantISO\(\) : null,\s*\n\s*pinned_at: archive \? null/);
  // Suppression confirmée par la modale partagée, jamais au clic direct.
  assert.match(app, /kind: 'rapport', id: r\.id,\s*\n\s*titre: t\('reports\.suppr\.titre'\)/);
  assert.match(app, /else if \(c\.kind === 'rapport'\) supprimerRapport\(c\.id\);/);
  // Supprimer le rapport qu'on suivait oublie le suivi : sinon le polling
  // interroge un 404 toutes les trois secondes.
  assert.match(app, /if \(suivi && suivi\.id === id\) oublierRapport\(\);/);
});

/* ---------------------------------------------------------------- */

test('11 — la comparaison ouvre deux rapports et synchronise par ratio', () => {
  assert.match(app, /function ReportsComparaison\(/);
  assert.match(app, /reportsState === 'comparaison'/);
  // Les deux rapports sont lus en entier : la liste ne porte pas le contenu.
  assert.match(app, /Promise\.all\(\[axRapport\(idA\), axRapport\(idB\)\]\)/);
  // Ratio et non pixels : deux rapports n'ont pas la même hauteur.
  assert.match(app, /dst\.scrollTop = \(src\.scrollTop \/ courseSrc\) \* courseDst;/);
  // Garde anti-boucle du défilement programmé.
  assert.match(app, /enCoursRef\.current = true;[\s\S]{0,400}requestAnimationFrame/);
  // Comparer un rapport avec lui-même n'a pas de sens : le second clic annule.
  assert.match(app, /if \(r\.id === comparaisonAttente\) \{ setComparaisonAttente\(null\); return; \}/);
  // Les deux colonnes passent par le MÊME rendu que l'éditeur.
  assert.match(app, /function ReportsComparaison[\s\S]{0,3000}<MarkdownView text=\{rapport\.content\}/);
  assert.match(css, /\.rep-compare \{[\s\S]{0,200}grid-template-columns: minmax\(0, 1fr\) minmax\(0, 1fr\);/);
});

test('12 — l’éditeur porte coût, export, livraison, partage et relance', () => {
  // Pastille de coût : la même fonction que les conversations.
  assert.match(app, /const cout = \(data && typeof data\.credits === 'number'\) \? texteCout\(\{/);
  // Export : les trois formats.
  for (const cle of ['reports.export.pdf', 'reports.export.md', 'reports.export.docx']) {
    assert.ok(app.includes(`'${cle}'`), cle);
  }
  assert.match(app, /exporter\('pdf'\)/);
  assert.match(app, /exporter\('md'\)/);
  assert.match(app, /exporter\('docx'\)/);
  // Livraison : une entrée par fournisseur CONNECTÉ, et l'identifiant du
  // fournisseur Drive est `google` (celui du backend), pas `google_drive`.
  assert.match(app, /outils\.notion && outils\.notion\.connecte[\s\S]{0,200}livrer\('notion'\)/);
  assert.match(app, /outils\.google && outils\.google\.connecte[\s\S]{0,200}livrer\('google'\)/);
  // Partage : créer, copier, révoquer.
  assert.match(app, /function PanneauPartage\(/);
  assert.match(app, /axPartagerRapport\(rapportId\)/);
  assert.match(app, /axRevoquerPartage\(rapportId\)/);
  // L'URL complète est construite côté front : le serveur rend un chemin
  // relatif, parce que l'adresse publique du front n'est pas sa donnée.
  assert.match(app, /window\.location\.origin \+ chemin/);
  assert.match(app, /copierDansPressePapier\(urlComplete\)/);
  // « Modifier et relancer » et « Régénérer ».
  assert.match(app, /onModifierRelancer=\{modifierEtRelancerRapport\}/);
  assert.match(app, /onRegenerer=\{regenererRapport\}/);
  assert.match(app, /const regenererRapport = \(\) => relancerDepuisId\(/);
});

test('13 — la relance libère son verrou dans un `finally`', () => {
  // Sans le `finally`, la sortie sur `reconnexion` laissait les trois boutons
  // de l'écran « sources insuffisantes » désactivés à vie (revue Task 4).
  assert.match(app, /const relancerDepuisId = async[\s\S]{0,1400}\} finally \{[\s\S]{0,300}setRelanceEnCours\(false\);/);
});

test('14 — le lancement porte un signal et une clé d’idempotence', () => {
  assert.match(app, /\{ signal: controleur\.signal, idempotencyKey: cle \}/);
  // La clé voyage dans `args` : « Réessayer » rejoue LA MÊME, sinon un échec
  // réseau survenu après l'acceptation serveur ferait payer deux fois.
  assert.match(app, /args: \{ type, analysisType, prompt, cleIdempotence: cle \}/);
  assert.match(app, /const cle = cleIdempotence \|\| nouvelleCleIdempotence\(\);/);
  // Le contrôleur est libéré, et seulement le sien.
  assert.match(app, /if \(controleurRapportRef\.current === controleur\) controleurRapportRef\.current = null;/);
  // Le bridge envoie bien l'en-tête au flux.
  assert.match(bridge, /idempotencyKey \? \{ "X-Idempotency-Key": idempotencyKey \} : \{\}/);
});

test('15 — la reprise au montage est gardée contre l’obsolescence', () => {
  // Une réponse tardive de `GET /reports/{id}` ne doit pas écraser un état SSE
  // plus avancé, ni réécrire le stockage par-dessus (revue Task 4).
  // Le bloc est isolé AVANT d'être testé : une expression régulière qui
  // traverse tout le fichier finit par attraper le `let actif` de l'effet
  // suivant dès qu'on ajoute dix lignes au-dessus.
  const debut = app.indexOf('const repris = etatDepuisStockage(brut);');
  assert.ok(debut > 0, 'effet de reprise introuvable');
  const bloc = app.slice(debut, app.indexOf('}, [route]);', debut));
  assert.match(bloc, /let actif = true;/);
  assert.match(bloc, /if \(!actif\) return;/);
  assert.match(bloc, /return \(\) => \{ actif = false; \};/);
});

/* ---------------------------------------------------------------- */

test('16 — la tuile Google Drive n’apparaît que si le backend la déclare', () => {
  assert.match(app, /id: 'google', nom: 'Google Drive'/);
  assert.match(app, /logo: '\/logos\/google-drive\.svg'/);
  assert.match(app, /if \(o\.masquerSiNonConfigure && !s\.configure\) return null;/);
  // L'identifiant `google_drive` de la tuile commentée n'existe nulle part
  // côté serveur : il ne doit pas revenir.
  // (Le nom ne subsiste que dans le commentaire qui dit pourquoi il est faux.)
  assert.ok(!/'google_drive'|"google_drive"/.test(app),
    "l'identifiant google_drive ne doit pas réapparaître");
});

test('17 — la feuille d’impression masque l’outillage et coupe aux titres H2', () => {
  const bloc = /@media print \{[\s\S]*?\n\}/.exec(css);
  assert.ok(bloc, 'aucun bloc @media print');
  const p = bloc[0];
  for (const sel of ['.sidebar', '.topbar', '.rep-actions', '.rep-liste',
                     '.lang-pill', '.theme-toggle', '.rep-partage']) {
    assert.ok(p.includes(sel), `non masqué à l'impression : ${sel}`);
  }
  assert.match(p, /background: #fff !important/);
  assert.match(p, /font-size: 12pt/);
  assert.match(p, /\.rep-doc h2 \{ page-break-before: always/);
  // Le premier H2 est excepté, sinon le document ouvre sur une page blanche.
  assert.match(p, /\.rep-doc h2:first-child \{ page-break-before: avoid/);
  assert.match(p, /\.rep-doc table[\s\S]{0,200}page-break-inside: avoid/);
  assert.match(p, /width: 100% !important/);
  assert.match(p, /@page \{ margin/);
});

/* ---------------------------------------------------------------- */

test('18 — la page publique est un rendu serveur, sans état ni indexation', () => {
  assert.ok(!/["']use client["']/.test(pagePublique),
    'la page publique doit rester un composant serveur');
  // Aucun état React : pas de hook.
  assert.ok(!/useState|useEffect|useRef/.test(pagePublique),
    'aucun état client sur la page publique');
  assert.match(pagePublique, /robots: \{ index: false, follow: false \}/);
  // Lecture serveur du rapport public, sans cache : un lien révoqué rend 404
  // tout de suite.
  /* Lecture SSR par l'URL INTERNE (revue finale, F9) : `NEXT_PUBLIC_API_URL`
     vaut l'URL publique en production, donc le VPS faisait un aller-retour
     DNS + TLS + proxy vers son propre nom pour joindre un backend qui écoute
     sur 127.0.0.1. Les IMAGES, elles, gardent l'URL publique : c'est le
     navigateur du visiteur qui les charge. */
  assert.match(pagePublique, /\$\{API_INTERNE\}\/partage\/\$\{encodeURIComponent\(jeton\)\}/);
  assert.match(pagePublique, /const API_INTERNE = process\.env\.API_INTERNE_URL/);
  assert.match(pagePublique, /\|\| process\.env\.NEXT_PUBLIC_API_URL/);
  assert.match(pagePublique, /\$\{API_PUBLIQUE\}\/viz\//);
  assert.ok(!/API_INTERNE\}\/viz\//.test(pagePublique),
    "les images doivent garder l'URL publique");
  assert.match(pagePublique, /cache: "no-store"/);
  // Un segment qui ne peut pas porter de jeton reste un 404 de routage.
  assert.match(pagePublique, /if \(!jeton\) notFound\(\);/);
  /* 404 et panne sont DEUX écrans distincts, et chacun est tracé côté serveur
     avant d'être rendu (revue Task 5, finding 3) : une panne backend ne doit
     pas se lire « lien introuvable » sur tous les liens partagés. */
  assert.match(pagePublique, /if \(res\.status === 404\) return \{ etat: "revoque" \};/);
  assert.match(pagePublique, /etat === "panne"/);
  assert.match(pagePublique, /etat === "revoque"/);
  assert.match(pagePublique, /console\.error\("\[partage\] API injoignable"/);
  assert.match(pagePublique, /console\.error\(`\[partage\] API en erreur : HTTP \$\{res\.status\}`\)/);
  assert.match(pagePublique, /console\.error\("\[partage\] réponse illisible"/);
  // Aucune fuite : ni jeton, ni message d'exception dans ce que voit le visiteur.
  /* Le 404 ne prétend plus trancher entre « révoqué » et « n'a jamais
     existé » (revue finale, F15) : le backend rend 404 dans les deux cas,
     délibérément — répondre différemment dirait à qui essaie des jetons au
     hasard lesquels ont existé. Le `<title>` du `not-found.tsx` reprend
     désormais le titre mot pour mot. */
  assert.match(etatsPartage, /revoqueTitre: "Ce lien ne mène à aucun rapport"/);
  assert.ok(!/Demandez-lui un nouveau lien/.test(etatsPartage),
    "phrase incohérente avec le cas « n'a jamais existé »");
  assert.match(notFoundPartage, /title: "Ce lien ne mène à aucun rapport — Axial Intelligence"/);
  assert.ok(!/Lien expiré/.test(notFoundPartage), 'le <title> disait « expiré »');
  // « 1 source » et non « 1 sources ».
  assert.match(etatsPartage, /sourcesSuffixeUn: "source"/);
  assert.match(pagePublique, /compterSources\(sources\.length\)/);
  assert.match(etatsPartage, /panneTitre: "Service indisponible"/);
  /* Textes français figés (spec §0, pas de `t()` ici) mais RASSEMBLÉS dans un
     seul objet, partagé avec le `not-found.tsx` de la route : l'arbitrage est
     visible et indexable par langue le jour où le partage devra suivre celle
     du rapport (revue Task 5, finding 5). */
  assert.match(etatsPartage, /^export const TEXTES = \{/m);
  assert.match(pagePublique, /import \{ APP, PageEtat, TEXTES, compterSources \} from "\.\.\/\.\.\/etats"/);
  // Aucun texte en dur ne subsiste dans le corps de la page.
  assert.ok(!/Rapport partagé par \{pseudo\}|>Sources<|Rapport produit par </.test(pagePublique),
    'un texte en dur subsiste hors de TEXTES');
  /* Le lien révoqué rend un VRAI 404 (le `not-found.tsx` du segment), pas une
     page polie en 200 : le `noindex` ne dit rien du code de statut. */
  assert.match(pagePublique, /if \(lu\.etat === "revoque"\) notFound\(\);/);
  assert.match(notFoundPartage, /PageEtat titre=\{TEXTES\.revoqueTitre\}/);
  assert.match(notFoundPartage, /import "\.\.\/\.\.\/partage\.css"/);
  // Le MÊME parseur que l'application.
  assert.match(pagePublique, /import \{ parserMarkdown \} from "\.\.\/\.\.\/\.\.\/_prototype\/markdown\.js"/);
  // Graphiques : l'image de l'API avec le jeton de partage en paramètre.
  assert.match(pagePublique, /\/viz\/\$\{encodeURIComponent\(viz\.empreinte\)\}\.svg\?p=\$\{encodeURIComponent\(jeton\)\}/);
  // En-tête et lien de retour.
  assert.match(pagePublique, /\{TEXTES\.partagePar\} \{pseudo\}/);
  assert.match(etatsPartage, /export const APP = "https:\/\/app\.axial-ia\.fr"/);
  assert.match(pagePublique, /href=\{APP\}/);
  // Le pseudo vient du SERVEUR, pas du segment d'URL (retapable à la main).
  assert.match(pagePublique, /const pseudo = rapport\.pseudo \|\| params\.pseudo;/);
  // Les liens sortants d'un rapport public ne transmettent rien.
  assert.match(pagePublique, /rel="nofollow noopener noreferrer"/);
});

test('19 — la feuille de la page publique suit le thème du visiteur', () => {
  // Le visiteur n'a aucun réglage chez nous : c'est `prefers-color-scheme` qui
  // décide, et rien d'autre (l'app, elle, bascule sur `html[data-theme]`).
  assert.match(cssPartage, /@media \(prefers-color-scheme: light\)/);
  assert.match(cssPartage, /\.partage-page \{[\s\S]{0,600}--rp-bg: #07050f;/);
  assert.match(cssPartage, /@media \(prefers-color-scheme: light\) \{\s*\n?\s*\.partage-page \{[\s\S]{0,400}--rp-bg: #f7f5f2;/);
  /* Aucune règle GLOBALE, en particulier aucun `body { … }` : la feuille est
     importée par une route, une règle globale survivrait à une navigation
     client hors de `/p/…` (revue Task 5, finding 6). Chaque sélecteur de
     premier niveau part donc de `.partage-page`. */
  assert.ok(!/(^|\n)\s*(body|html)\s*[,{]/.test(cssPartage),
    'la feuille publique ne doit porter aucune règle sur body / html');
  for (const ligne of cssPartage.split('\n')) {
    if (/^[.#a-zA-Z\[]/.test(ligne) && ligne.includes('{')) {
      assert.ok(ligne.startsWith('.partage-page'),
        `règle non portée par .partage-page : ${ligne}`);
    }
  }
  // Le fond est peint sur la racine, dans les DEUX schémas (via --rp-bg).
  assert.match(cssPartage, /\.partage-page \{[\s\S]{0,400}background: var\(--rp-bg\);/);
  // Aucune classe de l'application : la page ne dépend pas de `globals.css`.
  assert.ok(!/\.rep-|\.conv-|\.surface\b/.test(cssPartage),
    'la feuille publique ne doit pas dépendre des classes de l\'app');
  // Un tableau large défile dans sa boîte, pas dans la page.
  assert.match(cssPartage, /\.partage-page \.rp-table-wrap \{ overflow-x: auto/);
});

/* ---------------------------------------------------------------- */

test('20 — parité FR/EN des clés ajoutées par ce lot', () => {
  const cles = [
    'reports.liste.titre', 'reports.liste.recherche', 'reports.liste.vide',
    'reports.liste.charger_plus', 'reports.liste.chargement',
    'reports.menu.aide', 'reports.menu.comparer',
    'reports.suppr.titre', 'reports.suppr.detail',
    'reports.badge.termine', 'reports.badge.degrade', 'reports.badge.echec',
    'reports.badge.annule', 'reports.cout.pastille',
    'reports.compare.titre', 'reports.compare.choisir',
    'reports.compare.annuler_choix', 'reports.compare.sortir',
    'reports.compare.sync', 'reports.compare.chargement',
    'reports.export.menu', 'reports.export.pdf', 'reports.export.md',
    'reports.export.docx', 'reports.export.encours',
    'reports.livrer.menu', 'reports.livrer.notion', 'reports.livrer.drive',
    'reports.partage.ouvrir', 'reports.partage.titre', 'reports.partage.body',
    'reports.partage.creer', 'reports.partage.creation', 'reports.partage.copier',
    'reports.partage.copie', 'reports.partage.revoquer', 'reports.partage.revoque',
    'reports.editor.modifier_relancer', 'reports.editor.regenerer',
    'reports.editor.regeneration',
    // Sections au masculin, propres aux rapports (les clés des conversations
    // sont au féminin) — et l'aide de recherche qui parle de rapports.
    'reports.section.epingles', 'reports.section.recents', 'reports.section.archives',
    'reports.dossier.vide', 'reports.recherche.min',
  ];
  // Le dictionnaire est `{ fr: {...}, en: {...} }` : on découpe sur la borne
  // `en:` du littéral pour compter les clés d'une langue à la fois.
  const bloc = app.slice(app.indexOf('const STRINGS'), app.indexOf('window.AXIAL_I18N'));
  const borne = bloc.indexOf('\n  en: {');
  assert.ok(borne > 0, 'borne du dictionnaire anglais introuvable');
  const parLangue = { fr: bloc.slice(0, borne), en: bloc.slice(borne) };
  for (const cle of cles) {
    for (const langue of ['fr', 'en']) {
      assert.ok(parLangue[langue].includes(`'${cle}'`),
        `clé manquante en ${langue} : ${cle}`);
    }
  }
});

test('21 — les clés et le CSS du sélecteur de profondeur sont intacts', () => {
  // Arbitrage §0 : préparés, non branchés, CONSERVÉS.
  for (const cle of ['reports.depth', 'reports.depth.scan', 'reports.depth.standard',
                     'reports.depth.deep']) {
    assert.ok(app.includes(`'${cle}'`), `clé de profondeur retirée : ${cle}`);
  }
  assert.match(css, /\.rep-depth-seg \{/);
});

/* ---------------- Task 6 : nettoyage et correctifs de revue ---------------- */

test('22 — le CSS de l’éditeur trois colonnes jamais construit est retiré', () => {
  /* Classes du bilan §6, vérifiées absentes de la FEUILLE. Celles que les
     Tasks 2-5 ont finalement câblées (`.rep-gen-side`, `.rep-gen-progress*`,
     `.task*`, `.source-card*`, `.gap-callout*`) ne sont PAS du code mort :
     test 23 les protège. */
  for (const classe of ['.rep-rail', '.rep-rail-section', '.rep-rail-tabs',
                        '.rep-outline', '.rep-outline-label', '.rep-outline-item',
                        '.rep-suggest', '.rep-suggest-icon', '.rep-suggest-body',
                        '.rep-suggest-label', '.rep-suggest-actions',
                        '.rep-chart', '.rep-chart-title',
                        '.rep-source-counter',
                        '.confidence-row', '.confidence-bar', '.confidence-fill',
                        '.rep-editor']) {
    assert.ok(!css.includes(classe + ' ') && !css.includes(classe + ','),
      `CSS mort encore présent : ${classe}`);
  }
  // Et aucune de ces classes n'est rendue nulle part (la raison du retrait).
  for (const nom of ['rep-rail', 'rep-outline', 'rep-suggest', 'rep-chart',
                     'rep-source-counter', 'confidence-row', 'confidence-fill']) {
    assert.ok(!app.includes(nom), `classe retirée mais encore rendue : ${nom}`);
  }
});

test('23 — le CSS réellement rendu par les Tasks 2-5 est conservé', () => {
  /* Le bilan §6 datait d'AVANT l'écran de génération : ces classes y étaient
     listées comme mortes, elles sont désormais rendues. Les supprimer aurait
     dépouillé l'écran de suivi. */
  for (const classe of ['.rep-gen-side', '.rep-gen-progress', '.task-list',
                        '.task-dot', '.task-body', '.task-title', '.task-meta',
                        '.source-card', '.gap-callout', '.rep-doc']) {
    assert.ok(css.includes(classe), `CSS vivant supprimé par erreur : ${classe}`);
    assert.ok(app.includes(classe.slice(1)), `classe non rendue : ${classe}`);
  }
});

test('24 — les clés i18n de l’éditeur trois colonnes sont retirées', () => {
  /* `gap.*` / `conflict.*` étaient déjà parties avec la Task 2 ; restaient les
     trois clés du rail. `reports.editor.sources` est CONSERVÉE — et désormais
     réellement appelée, l'étiquette était en dur. */
  for (const cle of ['reports.gap.title', 'reports.gap.body', 'reports.gap.add',
                     'reports.gap.deepen', 'reports.gap.confidence',
                     'reports.conflict.title', 'reports.conflict.body',
                     'reports.conflict.recommendation', 'reports.conflict.use_a',
                     'reports.conflict.use_b', 'reports.conflict.cite_both',
                     'reports.editor.outline', 'reports.editor.activity',
                     'reports.editor.suggest']) {
    assert.ok(!app.includes(`'${cle}'`), `clé i18n morte encore déclarée : ${cle}`);
  }
  assert.match(app, /\{t\('reports\.editor\.sources'\)\}/);
});

test('25 — « Retirer du dossier » est offert quand le rapport est rangé', () => {
  // Capacité du bridge sans affordance jusqu'ici (revue Task 5, finding 8).
  assert.match(app, /cle: '__retirer', libelle: t\('conv\.menu\.retirer_dossier'\)/);
  assert.match(app, /gestion\.deplacer\(r\.id, null\)/);
  assert.match(app, /\.\.\.\(r\.project_id \? \[\{/);
  for (const langue of ['fr', 'en']) {
    const bloc = app.slice(app.indexOf('const STRINGS'), app.indexOf('window.AXIAL_I18N'));
    const borne = bloc.indexOf('\n  en: {');
    const partie = langue === 'fr' ? bloc.slice(0, borne) : bloc.slice(borne);
    assert.ok(partie.includes("'conv.menu.retirer_dossier'"), `clé absente en ${langue}`);
  }
});

test('26 — un envoi raté passe par decrireErreur et CarteErreur', () => {
  /* Dernier endroit de l'écran Rapports à afficher un `e.message` brut
     (revue Task 5, finding 10). */
  const editeur = app.slice(app.indexOf('function ReportsEditor('),
                            app.indexOf('function ReportsComparaison('));
  assert.ok(editeur.length > 1000, 'corps de ReportsEditor introuvable');
  assert.ok(!/\(e && e\.message\)/.test(editeur),
    'un message d\'exception brut subsiste dans ReportsEditor');
  assert.match(editeur, /setErreurLivraison\(\{ erreur: decrireErreur\(e, t\), provider \}\)/);
  assert.match(editeur, /<CarteErreur erreur=\{erreurLivraison\.erreur\} onAction=\{actionErreurLivraison\}/);
  // « Réessayer » relance LE MÊME fournisseur ; une session expirée reconnecte.
  assert.match(editeur, /if \(courant\.erreur\.action === 'reessayer'\) livrer\(courant\.provider\);/);
  assert.match(app, /onSessionExpiree=\{sessionExpiree\}/);
});

test('27 — une relance porte une clé d’idempotence, reportée par « Réessayer »', () => {
  // Même risque de double débit que le lancement (revue Task 5, finding 11).
  assert.match(app, /const cle = opts\.cleIdempotence \|\| nouvelleCleIdempotence\(\);/);
  assert.match(app, /axRelancerRapport\(id, \{ \.\.\.opts, idempotencyKey: cle \}\)/);
  assert.match(app, /relance: \{ id, options: \{ \.\.\.opts, cleIdempotence: cle \} \}/);
  assert.match(app, /if \(erreur\.action === 'reessayer' && relance\) \{/);
  // L'en-tête part bien sur la requête, et seulement si une clé est fournie.
  assert.match(bridge, /axRelancerRapport\(id, \{ question, elargir, forcer, idempotencyKey \} = \{\}\)/);
  assert.match(bridge, /headers: idempotencyKey \? \{ "X-Idempotency-Key": idempotencyKey \} : undefined,/);
});

test('28 — la longueur du jeton renvoie explicitement à la constante backend', () => {
  const jetonJs = readFileSync(new URL('../app/p/jeton.js', import.meta.url), 'utf8');
  // Le couplage doit être LISIBLE pour qui touchera `JETON_OCTETS`.
  assert.match(jetonJs, /JETON_LONGUEUR/);
  assert.match(jetonJs, /app\/modules\/reports\/service\.py/);
  // Le motif est construit depuis la constante : pas de « 22 » écrit deux fois.
  assert.match(jetonJs, /new RegExp\(`\^\[A-Za-z0-9_-\]\{\$\{LONGUEUR_JETON\}\}\$`\)/);
});
