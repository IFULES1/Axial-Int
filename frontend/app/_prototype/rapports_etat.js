"use client";
/* rapports_etat.js — la ligne de rapport EST l'état de l'écran de génération.
 *
 * Module PUR : aucune dépendance à React, au réseau, au navigateur. Il y a
 * trois entrées possibles pour le même état (un événement SSE, une lecture
 * `GET /reports/{id}`, une reprise depuis `localStorage`) et il n'y en avait
 * aucune forme commune : l'écran lisait `genMeta.step`/`genMeta.progress`
 * (vocabulaire du flux) alors que la liste et le polling lisent
 * `statut`/`etape`/`progression` (vocabulaire de la base). Deux découpages
 * pour la même chose, donc deux bugs à corriger à chaque changement.
 *
 * Ici, une seule forme :
 *   { id, statut, etape, progression, detail, question, titre, debut }
 * et un réducteur testable en Node (frontend/tests/etapes.test.mjs).
 */

// Statuts de la colonne `reports.statut` (app/modules/reports/models.py).
export const EN_COURS = 'en_cours';
export const TERMINE = 'termine';
export const ECHEC = 'echec';
export const DEGRADE = 'degrade';
export const ANNULE = 'annule';
export const SOURCES_INSUFFISANTES = 'sources_insuffisantes';
/* Statut PUREMENT front (revue finale, F10) : la base ne le connaît pas, elle
   ne connaît que l'absence de ligne. Le rapport a été supprimé pendant sa
   génération — `GET /reports/{id}` rend 404. Le polling avalait ce 404 (« un
   aller-retour raté n'interrompt pas le suivi »), ce qui est juste pour une
   coupure réseau et faux pour une suppression : le sablier tournait
   indéfiniment sur un rapport qui n'existait plus. */
export const SUPPRIME = 'supprime';

export const STATUTS_TERMINAUX = [TERMINE, ECHEC, DEGRADE, ANNULE,
                                  SOURCES_INSUFFISANTES, SUPPRIME];

/** Clé de reprise après rechargement de page. */
export const CLE_STOCKAGE = 'axial_rapport_en_cours';

/** Un statut terminal ferme le chrono et le polling. Tout statut inconnu est
 *  traité comme « en cours » : mieux vaut continuer à interroger le serveur
 *  qu'abandonner un rapport payé sur un mot qu'on ne connaît pas. */
export function estTerminal(statut) {
  return STATUTS_TERMINAUX.indexOf(statut) !== -1;
}

/** Raisons de `detail.raison` qui méritent un bandeau (spec §3). */
export const RAISONS_BANDEAU = [
  'truncated_generation', 'llm_unavailable', 'empty_generation',
  'investors_unavailable', 'couverture_partielle', 'generation_failed',
  'delai_depasse', 'annule_par_utilisateur',
  // Rapport supprimé pendant sa génération (revue finale, F10).
  'rapport_supprime',
];

/** `ReportOut` / `ReportDetail` → état d'écran.
 *
 *  Sert pour `GET /reports/{id}` (reprise, polling), pour une ligne de la
 *  liste « Vos rapports » cliquée pendant sa génération, et pour le rapport
 *  rendu par « Recherche élargie » / « Générer quand même ».
 */
export function etatDepuisRapport(rapport) {
  if (!rapport || !rapport.id) return null;
  return {
    id: String(rapport.id),
    statut: rapport.statut || EN_COURS,
    etape: rapport.etape || null,
    progression: typeof rapport.progression === 'number' ? rapport.progression : 0,
    detail: (rapport.detail && typeof rapport.detail === 'object') ? rapport.detail : {},
    question: rapport.question || null,
    titre: rapport.title || null,
    annulationDemandee: !!rapport.annulation_demandee,
    // Instant de création de la LIGNE : c'est l'origine du chronomètre. Sans
    // lui, un rechargement de page remettait le compteur à zéro et annonçait
    // « 0:03 » sur un rapport lancé depuis six minutes.
    debut: rapport.created_at || null,
    // Instant de FIN, quand il y en a un : c'est ce qui fige le chronomètre
    // d'un rapport terminé. Sans lui, l'écran d'échec voyait son compteur
    // repartir d'un cran à chaque rendu incident (revue Task 4, finding 4).
    fin: rapport.termine_at || null,
  };
}

/** État de départ, avant le premier événement : la question est déjà connue,
 *  l'identifiant ne l'est pas (il arrive avec le premier événement). */
export function etatAuLancement(question) {
  return {
    id: null, statut: EN_COURS, etape: null, progression: 0,
    detail: {}, question: question || null, titre: null,
    annulationDemandee: false, debut: new Date().toISOString(), fin: null,
  };
}

/** Réducteur : (état, événement SSE) → état.
 *
 * Contrat des événements (app/modules/analysis/service.py:stream_analysis) :
 * chacun porte `progress`, `step`, `etape`, `report_id`, `detail` ; le dernier
 * porte `done: true` avec soit `statut` + `data` (le `ReportDetail` complet +
 * `balance`), soit `error` + `code`.
 *
 * Deux subtilités assumées :
 *  - `code: 'delai_depasse'` sur le `done` ne dit PAS que le rapport a échoué :
 *    c'est le SUIVI qui a renoncé (le générateur borne sa boucle). La tâche,
 *    elle, tourne encore. On reste donc `en_cours` pour que le polling prenne
 *    le relais — passer en `echec` afficherait un échec inventé sur un rapport
 *    qui finit très bien deux minutes plus tard.
 *  - `detail` est réécrit entier par le backend à chaque étape (fusion faite en
 *    base) ; un `detail` vide n'écrase donc jamais ce qu'on avait.
 */
export function etatDepuisEvenement(etat, evt) {
  const base = etat || etatAuLancement(null);
  if (!evt || typeof evt !== 'object') return base;

  const suivant = Object.assign({}, base);
  if (evt.report_id) suivant.id = String(evt.report_id);
  if (typeof evt.progress === 'number') {
    suivant.progression = Math.max(0, Math.min(100, evt.progress));
  }
  // `etape: null` arrive sur `start` : ne pas effacer une étape déjà connue.
  if (evt.etape) suivant.etape = evt.etape;
  if (evt.detail && typeof evt.detail === 'object'
      && Object.keys(evt.detail).length) {
    suivant.detail = evt.detail;
  }

  if (!evt.done) return suivant;

  if (evt.error) {
    if (evt.code === 'delai_depasse') {
      // Le suivi abandonne, pas la génération : on retombe sur le polling.
      suivant.statut = EN_COURS;
      suivant.suiviAbandonne = true;
      return suivant;
    }
    suivant.statut = ECHEC;
    suivant.progression = 100;
    // Le flux ne rend pas de `termine_at` sur une erreur : l'instant où il la
    // rapporte est la meilleure approximation, et il fige le chronomètre.
    suivant.fin = suivant.fin || new Date().toISOString();
    suivant.detail = Object.assign({}, suivant.detail, {
      raison: evt.code || 'echec_generation',
      message: evt.error,
    });
    return suivant;
  }

  // `done` normal : `data` est un `ReportDetail` complet — il fait autorité sur
  // tout ce que les événements intermédiaires avaient accumulé.
  if (evt.data && evt.data.id) {
    const depuisData = etatDepuisRapport(evt.data);
    return Object.assign(depuisData, {
      progression: 100, debut: depuisData.debut || suivant.debut || null,
    });
  }
  suivant.statut = evt.statut || TERMINE;
  suivant.progression = 100;
  suivant.fin = suivant.fin || new Date().toISOString();
  return suivant;
}

/** Reprise après rechargement : ce qu'on a écrit dans `localStorage`.
 *  Tolère tout (clé absente, JSON cassé, objet sans `id`) — une reprise ratée
 *  ne doit jamais empêcher l'application de s'afficher. */
export function etatDepuisStockage(brut) {
  if (!brut || typeof brut !== 'string') return null;
  let objet;
  try { objet = JSON.parse(brut); } catch (e) { return null; }
  if (!objet || typeof objet !== 'object' || !objet.id) return null;
  return {
    id: String(objet.id),
    statut: objet.statut || EN_COURS,
    etape: objet.etape || null,
    progression: typeof objet.progression === 'number' ? objet.progression : 0,
    detail: (objet.detail && typeof objet.detail === 'object') ? objet.detail : {},
    question: objet.question || null,
    titre: objet.titre || null,
    annulationDemandee: !!objet.annulationDemandee,
    debut: objet.debut || null,
    fin: objet.fin || null,
  };
}

/** Ce qu'on écrit dans `localStorage` : le strict nécessaire pour rouvrir
 *  l'écran avant la première réponse de `GET /reports/{id}`. Le contenu du
 *  rapport n'y entre jamais — il fait des dizaines de kilo-octets et le
 *  serveur l'a déjà. */
export function versStockage(etat) {
  if (!etat || !etat.id) return null;
  return JSON.stringify({
    id: etat.id, statut: etat.statut, etape: etat.etape,
    progression: etat.progression, detail: etat.detail,
    question: etat.question, titre: etat.titre,
    annulationDemandee: etat.annulationDemandee, debut: etat.debut || null,
    fin: etat.fin || null,
  });
}

/** Ordre des étapes réelles du moteur — sert aussi à savoir laquelle est
 *  passée (coche) et laquelle est en cours (point). */
export const ETAPES = ['recherche', 'selection', 'couverture', 'redaction',
                       'finalisation'];

/** Libellé de l'étape en cours, chiffres réels compris.
 *
 * `t` est la fonction d'i18n de l'application ; l'interpolation est faite ici
 * (`t()` ne sait remplacer que `{credits}`), ce qui garde ce module utilisable
 * dans un test Node avec un `t` bouchonné.
 */
export function libelleEtape(etat, t) {
  const detail = (etat && etat.detail) || {};
  const etape = etat && etat.etape;
  const nombre = (cle, valeur) => String(t(cle)).replace('{n}', String(valeur));

  if (etape === 'recherche') {
    return detail.sources_trouvees != null
      ? nombre('reports.etape.recherche_n', detail.sources_trouvees)
      : t('reports.etape.recherche');
  }
  if (etape === 'selection') {
    return detail.sources_retenues != null
      ? nombre('reports.etape.selection_n', detail.sources_retenues)
      : t('reports.etape.selection');
  }
  if (etape === 'couverture') return t('reports.etape.couverture');
  if (etape === 'redaction') {
    return detail.section
      ? String(t('reports.etape.redaction_section')).replace('{section}', detail.section)
      : t('reports.etape.redaction');
  }
  if (etape === 'finalisation') return t('reports.etape.finalisation');
  return t('reports.etape.demarrage');
}

/** État d'un rapport disparu pendant sa génération (revue finale, F10).
 *
 *  Conserve l'identifiant et la question — l'écran doit pouvoir proposer
 *  « relancer la même question » — et pose la raison qui nomme le bandeau.
 *  Appelé sur un 404 du polling ET sur le `code: "rapport_supprime"` du flux :
 *  les deux chemins mènent au même écran.
 */
export function etatSupprime(etat) {
  return {
    ...(etat || {}),
    statut: SUPPRIME,
    progression: 100,
    detail: { ...((etat && etat.detail) || {}), raison: 'rapport_supprime' },
  };
}

/** Libellé du bandeau d'un rapport dégradé / partiel (spec §3).
 *  Renvoie `null` quand il n'y a rien à signaler — un rapport complet ne porte
 *  pas de bandeau. */
export function libelleRaison(etat, t) {
  const detail = (etat && etat.detail) || {};
  const statut = etat && etat.statut;
  const raison = detail.raison;
  if (statut !== DEGRADE && !(raison && RAISONS_BANDEAU.indexOf(raison) !== -1)) {
    return null;
  }
  const cle = raison && RAISONS_BANDEAU.indexOf(raison) !== -1
    ? `reports.degrade.${raison}`
    : 'reports.degrade.defaut';
  return t(cle);
}
