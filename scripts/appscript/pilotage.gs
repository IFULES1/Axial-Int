/**
 * Pilotage Axial — synchronisation automatique du classeur.
 *
 * Appelle l'API d'Axial et réécrit les onglets de données. Les onglets
 * rédigés à la main (LISEZ_MOI, METRIQUES, EVENEMENTS_A_TRACER) ne sont
 * JAMAIS touchés : une synchronisation qui écrase du contenu curé finit par
 * être désactivée par celui qui l'a subi une fois.
 *
 * Installation : voir le bas du fichier.
 */

// ---------------------------------------------------------------- réglages
var API = 'https://app.axial-ia.fr/api/metrics/export';

// Le jeton vit dans les propriétés du script, jamais dans le code : ce fichier
// se partage, se copie et se retrouve dans un historique de versions.
function jeton_() {
  var t = PropertiesService.getScriptProperties().getProperty('AXIAL_EXPORT_TOKEN');
  if (!t) {
    throw new Error(
      "Jeton absent. Extensions → Apps Script → Paramètres du projet → " +
      "Propriétés du script → ajoute AXIAL_EXPORT_TOKEN.");
  }
  return t;
}

// Onglets réécrits à chaque passage. Tout le reste est laissé intact.
var ONGLETS_DONNEES = ['UTILISATEURS', 'RAPPORTS', 'EMAILS', 'REVENUS', 'COUTS'];

// ---------------------------------------------------------------- entrée
function synchroniser() {
  var debut = new Date();
  var feuille = SpreadsheetApp.getActiveSpreadsheet();
  var lues = 0;

  try {
    var d = recuperer_();

    lues += ecrire_(feuille, 'UTILISATEURS', d.utilisateurs, [
      ['email', 'email'], ['categorie', 'Catégorie'], ['inscrit_le', 'Inscrit le'],
      ['derniere_connexion', 'Dernière connexion'], ['sessions', 'Sessions'],
      ['company_name', 'Entreprise'], ['sector', 'Secteur'],
      ['funding_stage', 'Stade'], ['target_market', 'Marché'], ['language', 'Langue'],
      ['rapports_produits', 'Rapports produits'], ['rapports_total', 'Rapports total'],
      ['questions', 'Questions'], ['documents', 'Documents'], ['outils', 'Outils'],
      ['veilles', 'Veilles'], ['solde_credits', 'Solde crédits'],
      ['essai_expire_le', 'Essai expire le'], ['abonnement', 'Abonnement'],
      ['renouvellement_bloque', 'Renouvellement bloqué']]);

    lues += ecrire_(feuille, 'RAPPORTS', d.rapports, [
      ['email', 'email'], ['produit_le', 'Produit le'], ['type', 'Type'],
      ['restaure', 'Restauré'], ['caracteres', 'Caractères'], ['sources', 'Sources'],
      ['duree_secondes', 'Durée (s)'], ['modele', 'Modèle'],
      ['tokens_entree', 'Tokens entrée'], ['tokens_sortie', 'Tokens sortie'],
      ['cout_modele_eur', 'Coût modèle (€)'], ['cout_recherche_eur', 'Coût recherche (€)'],
      ['appels_recherche', 'Appels recherche']]);

    lues += ecrire_(feuille, 'EMAILS', d.emails, [
      ['campagne', 'Campagne'], ['premier_envoi', 'Premier envoi'],
      ['envoyes', 'Envoyés'], ['ouvertures_apparentes', 'Ouvertures apparentes'],
      ['lectures_reelles', 'Lectures réelles'], ['jamais_ouverts', 'Jamais ouverts']]);

    lues += ecrire_(feuille, 'REVENUS', d.revenus, [
      ['email', 'email'], ['plan', 'Plan'], ['statut', 'Statut'],
      ['annule_en_fin_de_periode', 'Annulé en fin de période'],
      ['fin_periode', 'Fin de période'], ['stripe_reel', 'Stripe réel']]);

    // Les coûts arrivent comme un objet {poste: {...}} et non comme une liste.
    var couts = [];
    for (var poste in d.couts_agreges) {
      var c = d.couts_agreges[poste];
      couts.push({poste: poste, lignes: c.lignes, mesurees: c.mesurees,
                  cout_modele_eur: c.cout_modele_eur,
                  cout_recherche_eur: c.cout_recherche_eur,
                  cout_eur: c.cout_eur});
    }
    lues += ecrire_(feuille, 'COUTS', couts, [
      ['poste', 'Poste'], ['lignes', 'Lignes'], ['mesurees', 'Mesurées'],
      ['cout_modele_eur', 'Coût modèle (€)'], ['cout_recherche_eur', 'Coût recherche (€)'],
      ['cout_eur', 'Coût total (€)']]);

    journal_(feuille, 'succès', lues, d.extrait_le, secondes_(debut), '');
  } catch (e) {
    // Une erreur est écrite dans le journal AVANT d'être relancée : sans ça,
    // une synchronisation qui échoue toutes les heures reste invisible.
    journal_(feuille, 'échec', lues, '', secondes_(debut), String(e).slice(0, 300));
    throw e;
  }
}

// ---------------------------------------------------------------- outils
function recuperer_() {
  var r = UrlFetchApp.fetch(API, {
    method: 'get',
    headers: {'X-Axial-Export-Token': jeton_()},
    muteHttpExceptions: true,
    followRedirects: true,
  });
  var code = r.getResponseCode();
  if (code !== 200) {
    throw new Error('API ' + code + ' : ' + r.getContentText().slice(0, 200));
  }
  return JSON.parse(r.getContentText());
}

function ecrire_(feuille, nom, lignes, colonnes) {
  var f = feuille.getSheetByName(nom) || feuille.insertSheet(nom);
  f.clear();

  var entetes = colonnes.map(function (c) { return c[1]; });
  var table = [entetes];
  (lignes || []).forEach(function (l) {
    table.push(colonnes.map(function (c) {
      var v = l[c[0]];
      if (v === null || v === undefined) return '';
      if (v === true) return 'oui';
      if (v === false) return '';
      return v;
    }));
  });

  f.getRange(1, 1, table.length, entetes.length).setValues(table);
  var tete = f.getRange(1, 1, 1, entetes.length);
  tete.setFontWeight('bold').setFontColor('#FFFFFF').setBackground('#2F4858');
  f.setFrozenRows(1);
  f.autoResizeColumns(1, entetes.length);
  return Math.max(0, table.length - 1);
}

function journal_(feuille, statut, lues, extrait_le, duree, erreur) {
  var f = feuille.getSheetByName('SYNC_LOG') || feuille.insertSheet('SYNC_LOG');
  if (f.getLastRow() === 0) {
    f.appendRow(['Horodatage', 'Statut', 'Lignes lues', 'Données extraites le',
                 'Durée (s)', 'Erreur']);
    f.getRange(1, 1, 1, 6).setFontWeight('bold')
      .setFontColor('#FFFFFF').setBackground('#2F4858');
    f.setFrozenRows(1);
  }
  f.appendRow([new Date(), statut, lues, extrait_le, duree, erreur]);
}

function secondes_(debut) {
  return Math.round((new Date() - debut) / 100) / 10;
}

// ---------------------------------------------------------------- menu
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Axial')
    .addItem('Synchroniser maintenant', 'synchroniser')
    .addItem('Activer la synchro horaire', 'activer_horaire')
    .addItem('Désactiver la synchro', 'desactiver')
    .addToUi();
}

function activer_horaire() {
  desactiver();
  ScriptApp.newTrigger('synchroniser').timeBased().everyHours(1).create();
  SpreadsheetApp.getUi().alert('Synchronisation activée : toutes les heures.');
}

function desactiver() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'synchroniser') ScriptApp.deleteTrigger(t);
  });
}

/**
 * INSTALLATION
 *
 * 1. Ouvre le classeur → Extensions → Apps Script.
 * 2. Colle ce fichier entier dans Code.gs, puis enregistre.
 * 3. Paramètres du projet (roue dentée) → Propriétés du script → Ajouter :
 *       nom   : AXIAL_EXPORT_TOKEN
 *       valeur: le jeton fourni séparément
 * 4. Recharge le classeur : un menu « Axial » apparaît.
 * 5. Axial → Synchroniser maintenant. Google demande une autorisation la
 *    première fois (le script lit une URL externe et écrit dans le classeur).
 * 6. Axial → Activer la synchro horaire.
 *
 * MAINTENANCE
 * - L'onglet SYNC_LOG enregistre chaque passage, succès comme échec.
 * - Si le jeton est révoqué côté Axial, la synchro échoue en 403 et le motif
 *   apparaît dans SYNC_LOG.
 * - Les onglets LISEZ_MOI, METRIQUES, DASHBOARD et EVENEMENTS_A_TRACER ne sont
 *   jamais réécrits : tes formules et tes commentaires y survivent.
 */
