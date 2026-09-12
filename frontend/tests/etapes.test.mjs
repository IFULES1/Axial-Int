// Task 4 — l'écran de génération est piloté par la LIGNE de rapport.
//
// Le réducteur `etatDepuisEvenement` est la seule traduction entre le
// vocabulaire du flux SSE (`progress`, `step`, `report_id`, `done`) et celui
// de la base (`statut`, `etape`, `progression`, `detail`). Il vit dans un
// module pur pour être testable ici, sans navigateur ni React : c'est la
// pièce dont une erreur fige silencieusement une barre de progression ou
// annonce un échec sur un rapport qui tourne encore.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  EN_COURS, TERMINE, ECHEC, DEGRADE, SOURCES_INSUFFISANTES, CLE_STOCKAGE,
  ETAPES, estTerminal, etatAuLancement, etatDepuisEvenement, etatDepuisRapport,
  etatDepuisStockage, versStockage, libelleEtape, libelleRaison,
} from '../app/_prototype/rapports_etat.js';

const racine = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(racine, 'app/_prototype/App.jsx'), 'utf8');
const bridge = readFileSync(join(racine, 'app/_prototype/bridge.js'), 'utf8');

/* Les deux dictionnaires i18n, extraits du littéral `STRINGS` d'App.jsx. */
function clesI18n(langue) {
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

/* `t` bouchonné : rend la clé telle quelle, ce qui rend les assertions
   lisibles ET vérifie au passage quelle clé le module demande. */
const tCle = (cle) => cle;
/* `t` qui rend le vrai texte français du dictionnaire de l'application. */
const dicoFr = clesI18n('fr');
const tFr = (cle) => (dicoFr.has(cle) ? dicoFr.get(cle).replace(/^'|',?$/g, '') : cle);

// --- 1. Le premier événement rend le rapport reprenable ---------------------

test('1 — `start` : l\'identifiant arrive dès le premier événement', () => {
  const etat = etatDepuisEvenement(etatAuLancement('Marché du lithium'), {
    progress: 5, step: 'start', etape: null, report_id: 'r-1', detail: {},
    message: 'Démarrage de l\'analyse…',
  });
  assert.equal(etat.id, 'r-1');
  assert.equal(etat.statut, EN_COURS);
  assert.equal(etat.progression, 5);
  assert.equal(etat.question, 'Marché du lithium');
  // `etape: null` sur `start` ne doit pas être pris pour une étape.
  assert.equal(etat.etape, null);
  assert.equal(libelleEtape(etat, tCle), 'reports.etape.demarrage');
});

// --- 2 & 3. Les étapes réelles, avec leurs chiffres réels -------------------

test('2 — `recherche` : le compte de sources trouvées est affiché', () => {
  let etat = etatDepuisEvenement(etatAuLancement('q'), {
    progress: 5, step: 'start', report_id: 'r-1', detail: {},
  });
  etat = etatDepuisEvenement(etat, {
    progress: 20, step: 'retrieve', etape: 'recherche', report_id: 'r-1',
    detail: { angles: 4, sources_trouvees: 37, message: '37 source(s) trouvée(s).' },
  });
  assert.equal(etat.etape, 'recherche');
  assert.equal(etat.progression, 20);
  assert.equal(libelleEtape(etat, tCle), 'reports.etape.recherche_n');
  // Interpolation faite dans le module : `t()` ne sait pas le faire.
  assert.match(libelleEtape(etat, tFr), /37/);
});

test('3 — `redaction` : la section en cours vient de `detail.section`', () => {
  const etat = etatDepuisEvenement(
    { id: 'r-1', statut: EN_COURS, etape: 'selection', progression: 35, detail: {} },
    {
      progress: 62, step: 'generate', etape: 'redaction', report_id: 'r-1',
      detail: { section: '3/8', message: 'Rédaction du rapport…' },
    },
  );
  assert.equal(etat.etape, 'redaction');
  assert.equal(libelleEtape(etat, tCle), 'reports.etape.redaction_section');
  assert.equal(libelleEtape(etat, tFr), 'Rédaction — section 3/8');
  // Étape connue du moteur : sans quoi la liste de tâches n'allumerait rien.
  assert.ok(ETAPES.includes(etat.etape));
});

test('4 — un `detail` vide n\'efface jamais ce qui était déjà connu', () => {
  const avant = etatDepuisEvenement(etatAuLancement('q'), {
    progress: 20, step: 'retrieve', etape: 'recherche', report_id: 'r-1',
    detail: { sources_trouvees: 12 },
  });
  const apres = etatDepuisEvenement(avant, {
    progress: 30, step: 'retrieve', etape: null, report_id: 'r-1', detail: {},
  });
  assert.equal(apres.detail.sources_trouvees, 12);
  assert.equal(apres.etape, 'recherche');   // `etape: null` ne remet pas à zéro
  assert.equal(apres.progression, 30);
  // Progression bornée : un backend qui enverrait 140 n'étirerait pas la barre.
  assert.equal(etatDepuisEvenement(apres, { progress: 140 }).progression, 100);
});

// --- 5 à 8. Les statuts terminaux -------------------------------------------

test('5 — `done` : `data` (le ReportDetail complet) fait autorité', () => {
  const etat = etatDepuisEvenement(
    { id: 'r-1', statut: EN_COURS, etape: 'redaction', progression: 62, detail: {} },
    {
      progress: 100, step: 'done', done: true, etape: 'finalisation',
      report_id: 'r-1', statut: TERMINE, detail: { credits: 25 },
      data: {
        id: 'r-1', title: 'Marché du lithium', statut: TERMINE,
        etape: 'finalisation', progression: 100, content: '## Synthèse',
        detail: { credits: 25 }, question: 'Marché du lithium',
        created_at: '2026-09-12T10:00:00Z', balance: 175,
      },
    },
  );
  assert.equal(etat.statut, TERMINE);
  assert.equal(etat.progression, 100);
  assert.equal(etat.titre, 'Marché du lithium');
  assert.equal(etat.debut, '2026-09-12T10:00:00Z');
  assert.ok(estTerminal(etat.statut));
  assert.equal(libelleRaison(etat, tCle), null);   // aucun bandeau sur un rapport complet
});

test('6 — `degrade` : le bandeau nomme la raison en clair', () => {
  const etat = etatDepuisEvenement({ id: 'r-1', statut: EN_COURS, progression: 90, detail: {} }, {
    progress: 100, step: 'done', done: true, report_id: 'r-1',
    statut: DEGRADE, degraded: true, detail: { raison: 'truncated_generation' },
    data: {
      id: 'r-1', title: 'Rapport', statut: DEGRADE, progression: 100,
      content: '…', detail: { raison: 'truncated_generation' },
    },
  });
  assert.equal(etat.statut, DEGRADE);
  assert.equal(libelleRaison(etat, tCle), 'reports.degrade.truncated_generation');

  // Un `termine` porteur d'une raison (couverture partielle : « Générer quand
  // même ») porte AUSSI son bandeau — le statut seul ne suffit pas.
  const partiel = etatDepuisRapport({
    id: 'r-2', title: 'x', statut: TERMINE, progression: 100,
    detail: { raison: 'couverture_partielle' },
  });
  assert.equal(libelleRaison(partiel, tCle), 'reports.degrade.couverture_partielle');
});

test('7 — `done` avec `error` : échec nommé, rien d\'inventé', () => {
  const etat = etatDepuisEvenement({ id: 'r-1', statut: EN_COURS, progression: 40, detail: {} }, {
    step: 'error', done: true, detail: {},
    error: 'Crédits insuffisants (10/25).', code: 'insufficient_credits',
  });
  assert.equal(etat.statut, ECHEC);
  assert.equal(etat.progression, 100);
  assert.equal(etat.detail.raison, 'insufficient_credits');
  assert.equal(etat.detail.message, 'Crédits insuffisants (10/25).');
  assert.ok(estTerminal(etat.statut));
});

test('8 — `delai_depasse` : le SUIVI abandonne, pas la génération', () => {
  // Le générateur SSE borne sa boucle sur la même échéance que le moteur. Ce
  // `done` dit « je ne regarde plus », pas « le rapport a échoué » : passer en
  // `echec` afficherait un échec inventé sur un rapport qui finit très bien
  // deux minutes plus tard, et pousserait à le relancer (donc à le payer deux
  // fois).
  const etat = etatDepuisEvenement({ id: 'r-1', statut: EN_COURS, progression: 70, detail: {} }, {
    progress: 100, step: 'done', done: true, report_id: 'r-1',
    code: 'delai_depasse', detail: {}, error: 'Le suivi de la génération a dépassé…',
  });
  assert.equal(etat.statut, EN_COURS);
  assert.equal(etat.suiviAbandonne, true);
  assert.equal(estTerminal(etat.statut), false);   // le polling prend le relais
});

test('9 — `sources_insuffisantes` : terminal, avec les sources trouvées', () => {
  const etat = etatDepuisEvenement({ id: 'r-1', statut: EN_COURS, progression: 45, detail: {} }, {
    progress: 100, step: 'done', done: true, report_id: 'r-1',
    statut: SOURCES_INSUFFISANTES, degraded: true,
    detail: { raison: 'sources_insuffisantes' },
    data: {
      id: 'r-1', title: 'x', statut: SOURCES_INSUFFISANTES, progression: 100,
      question: 'Marché du lithium en Mongolie',
      detail: {
        message: 'Les sources trouvées ne permettent pas…',
        sources: [{ titre: 'Un billet', url: 'https://ex.fr/a', domaine: 'ex.fr' }],
      },
    },
  });
  assert.equal(etat.statut, SOURCES_INSUFFISANTES);
  assert.ok(estTerminal(etat.statut));
  assert.equal(etat.detail.sources.length, 1);
  // La question est conservée : « Reformuler » la pré-remplit.
  assert.equal(etat.question, 'Marché du lithium en Mongolie');
});

// --- 10. Reprise après rechargement de page --------------------------------

test('10 — reprise depuis le stockage local : aller-retour complet', () => {
  const vivant = etatDepuisEvenement(etatAuLancement('Marché du lithium'), {
    progress: 62, step: 'generate', etape: 'redaction', report_id: 'r-42',
    detail: { section: '3/8', sources_trouvees: 37 },
  });
  const brut = versStockage(vivant);
  assert.ok(typeof brut === 'string');
  const repris = etatDepuisStockage(brut);
  assert.equal(repris.id, 'r-42');
  assert.equal(repris.statut, EN_COURS);
  assert.equal(repris.etape, 'redaction');
  assert.equal(repris.progression, 62);
  assert.equal(repris.question, 'Marché du lithium');
  assert.equal(repris.debut, vivant.debut);   // le chrono ne repart pas de zéro
  assert.equal(libelleEtape(repris, tFr), 'Rédaction — section 3/8');

  // Un état sans identifiant n'est pas stockable : rien à reprendre.
  assert.equal(versStockage(etatAuLancement('q')), null);
  assert.equal(versStockage(null), null);
});

test('11 — une reprise illisible ne casse rien', () => {
  for (const brut of [null, undefined, '', 'pas du json', '{}', '[]',
                      '{"statut":"en_cours"}', '{"id":null}']) {
    assert.equal(etatDepuisStockage(brut), null, `refusé : ${String(brut)}`);
  }
  // Un `detail` d'un autre type est ignoré, pas propagé tel quel.
  assert.deepEqual(etatDepuisStockage('{"id":"r-1","detail":"oups"}').detail, {});
});

test('12 — un rapport de la liste ouvre le même écran de suivi', () => {
  // `ReportOut` (liste) n'a ni `content` ni `detail` : l'état doit quand même
  // se construire, sinon cliquer sur une ligne « en cours » ne menait nulle part.
  const etat = etatDepuisRapport({
    id: 'r-7', title: 'Cartographie investisseurs', analysis_type: 'x',
    created_at: '2026-09-12T09:00:00Z', statut: EN_COURS, etape: 'selection',
    progression: 35,
  });
  assert.equal(etat.id, 'r-7');
  assert.equal(etat.statut, EN_COURS);
  assert.deepEqual(etat.detail, {});
  assert.equal(libelleEtape(etat, tCle), 'reports.etape.selection');
  assert.equal(etatDepuisRapport(null), null);
  assert.equal(etatDepuisRapport({ title: 'sans id' }), null);
});

test('13 — un événement illisible laisse l\'état intact', () => {
  const avant = { id: 'r-1', statut: EN_COURS, etape: 'recherche', progression: 20, detail: {} };
  assert.deepEqual(etatDepuisEvenement(avant, null), avant);
  assert.deepEqual(etatDepuisEvenement(avant, 'texte'), avant);
});

// --- 14 & 15. Garde-fous d'intégration -------------------------------------

test('14 — toute clé i18n demandée par le module existe en FR ET en EN', () => {
  const fr = clesI18n('fr');
  const en = clesI18n('en');
  const attendues = [
    'reports.etape.demarrage', 'reports.etape.recherche', 'reports.etape.recherche_n',
    'reports.etape.selection', 'reports.etape.selection_n', 'reports.etape.couverture',
    'reports.etape.redaction', 'reports.etape.redaction_section',
    'reports.etape.finalisation', 'reports.degrade.defaut', 'reports.degrade.titre',
    'reports.degrade.truncated_generation', 'reports.degrade.llm_unavailable',
    'reports.degrade.empty_generation', 'reports.degrade.investors_unavailable',
    'reports.degrade.couverture_partielle', 'reports.degrade.delai_depasse',
    'reports.degrade.annule_par_utilisateur', 'reports.degrade.generation_failed',
    'reports.gen.stop', 'reports.gen.navigate', 'reports.sources_insuf.reformuler',
    'reports.sources_insuf.elargir', 'reports.sources_insuf.forcer',
    'reports.signalement.ouvrir', 'reports.signalement.envoyer',
    'onb.premiere_analyse.delai',
  ];
  for (const cle of attendues) {
    assert.ok(fr.has(cle), `clé FR manquante : ${cle}`);
    assert.ok(en.has(cle), `clé EN manquante : ${cle}`);
  }
  // Les clés d'interpolation doivent porter leur marqueur, sinon le chiffre
  // réel disparaît silencieusement de l'écran.
  for (const langue of [fr, en]) {
    assert.match(langue.get('reports.etape.recherche_n'), /\{n\}/);
    assert.match(langue.get('reports.etape.selection_n'), /\{n\}/);
    assert.match(langue.get('reports.etape.redaction_section'), /\{section\}/);
  }
  // Écran crédits unique (spec §6) : les clés du composant supprimé aussi.
  for (const langue of ['fr', 'en']) {
    const dico = clesI18n(langue);
    for (const cle of [...dico.keys()]) {
      assert.ok(!cle.startsWith('reports.quota.'),
        `clé orpheline de ReportsQuota : ${langue}/${cle}`);
    }
  }
});

test('15 — le front a bien basculé sur le contrat de Task 3', () => {
  // `POST /reports` est réservé aux administrateurs : le repli d'archivage du
  // front rendrait 403.
  assert.ok(!/axCreateReport/.test(app), 'axCreateReport doit avoir disparu du front');
  assert.ok(!/axCreateReport/.test(bridge), 'axCreateReport doit avoir disparu du bridge');
  // `GET /reports` rend `{items, has_more}` : plus de liste nue.
  assert.ok(!/axListReports/.test(app) && !/axListReports/.test(bridge));
  assert.match(bridge, /export\s+async\s+function\s+axRapports/);
  // La fenêtre de liste est demandée avec sa borne et son drapeau d'archives
  // (Task 5 : « Charger plus » et la section « Archivés »).
  assert.match(app, /axRapports\(\{\s*limit:\s*20,\s*before,\s*inclure_archives:/);
  assert.match(app, /\(page && page\.items\) \|\| \[\]/);
  // `POST /analysis/run` rend un `ReportDetail` (`id`, plus `report_id`).
  assert.match(bridge, /report_id:\s*r\.id/);
  // Images viz : plus de `<img src>` direct, qui n'envoie aucun en-tête.
  assert.ok(!/\/viz\/\$\{[^}]*\}\.svg/.test(app),
    'plus d\'URL /viz/…svg construite dans App.jsx');
  assert.match(bridge, /export\s+async\s+function\s+axVizSvg/);
  assert.match(app, /URL\.createObjectURL/);
  assert.match(app, /URL\.revokeObjectURL/);
  // Le Google Form a disparu, remplacé par la route de feedback.
  assert.ok(!/docs\.google\.com/.test(app), 'le lien Google Form doit avoir disparu');
  assert.match(bridge, /reports\/\$\{id\}\/feedback/);
  // `ReportsQuota` supprimé, `ModaleCredits` à sa place.
  // Le nom ne subsiste que dans le commentaire qui explique sa disparition.
  assert.ok(!/(?:function|window\.|<)\s*ReportsQuota/.test(app),
    'ReportsQuota doit avoir disparu (déclaration, export ou rendu)');
  assert.match(app, /reportsState === 'sources'/);
  // Reprise : la clé de stockage utilisée par App.jsx est celle du module.
  assert.equal(CLE_STOCKAGE, 'axial_rapport_en_cours');
  assert.match(app, /RAPPORT_CLE_STOCKAGE/);
  // Polling 3 s et arrêt sur statut terminal.
  assert.match(app, /setInterval\([\s\S]{0,400}?axRapport\(idEnCours\)[\s\S]{0,400}?\}, 3000\)/);
  // Stop branché sur la route d'annulation.
  assert.match(bridge, /reports\/\$\{id\}\/annuler/);
  assert.match(bridge, /reports\/\$\{id\}\/relancer/);
});
