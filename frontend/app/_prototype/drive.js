/* drive.js — Google Picker (Sources v2 §6), module pur.
 *
 * Isolé d'App.jsx pour rester importable sous Node (frontend/tests/
 * drive.test.mjs) : aucune référence à `document`/`window`/`google` au
 * niveau du module, seulement à l'intérieur des fonctions — elles ne sont
 * donc évaluées qu'à l'appel, quand ces globales existent réellement (le
 * navigateur) ou ont été posées par le test.
 *
 * Le Picker EXIGE un jeton OAuth côté NAVIGATEUR (c'est Google qui l'impose,
 * indépendant du jeton serveur géré par `integrations.jeton_actif`) :
 * `google.accounts.oauth2.initTokenClient` en obtient un, scope
 * `drive.file`, jamais persisté ni envoyé au backend — seuls
 * `file_id`/`name`/`mime_type` partent vers `axImporterDepuisDrive`, qui
 * retélécharge côté serveur avec le jeton, lui, stocké.
 *
 * Revue Task 7, tour 1 : `requestAccessToken()` doit s'exécuter DANS le
 * geste utilisateur (clic), faute de quoi le navigateur bloque la popup de
 * consentement Google — GIS n'a alors aucun moyen d'aboutir. Les scripts
 * (`chargerGooglePicker`) doivent donc être chargés AVANT le clic (au
 * montage de la surface, dès que le bouton devient visible) ; le clic
 * n'attend plus qu'une promesse déjà résolue puis appelle
 * `requestAccessToken()` sans autre délai.
 */

export const GOOGLE_PICKER_SCOPE = 'https://www.googleapis.com/auth/drive.file';
// Formats acceptés par `documents.ingest` (PDF/DOCX/XLSX/CSV/TXT/MD) + les
// trois types Google natifs, exportés côté serveur (`telecharger_drive`).
export const GOOGLE_PICKER_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/csv',
  'text/plain',
  'text/markdown',
  'application/vnd.google-apps.document',
  'application/vnd.google-apps.spreadsheet',
  'application/vnd.google-apps.presentation',
].join(',');

let _googlePickerChargement = null;

/** Réservé aux tests : remet le chargement mémorisé à zéro entre deux cas. */
export function _reinitialiserChargementPourTests() {
  _googlePickerChargement = null;
}

/** Charge `api.js` (Picker) et `gsi/client` (jeton OAuth navigateur) à la
 * demande, une seule fois : la promesse est mémorisée pour tout appel
 * suivant, y compris un premier appel concurrent. Un échec de chargement
 * remet le cache à zéro (via `.catch`) pour qu'un essai ultérieur puisse
 * retenter, y compris pour l'appel concurrent qui reçoit le même rejet. */
export function chargerGooglePicker() {
  if (_googlePickerChargement) return _googlePickerChargement;
  const chargerScript = (src) => new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = src; s.async = true; s.defer = true;
    s.onload = res; s.onerror = () => rej(new Error(`Chargement de ${src} impossible`));
    document.head.appendChild(s);
  });
  _googlePickerChargement = Promise.all([
    chargerScript('https://apis.google.com/js/api.js')
      .then(() => new Promise((res) => window.gapi.load('picker', res))),
    chargerScript('https://accounts.google.com/gsi/client'),
  ]).catch((e) => { _googlePickerChargement = null; throw e; });
  return _googlePickerChargement;
}

/** Jeton OAuth navigateur (scope `drive.file`), obtenu dans le geste de
 * l'appelant : `client.requestAccessToken()` doit être invoqué
 * synchroniquement depuis le clic, jamais après un `await` réseau, sous
 * peine de blocage de popup par le navigateur. `error_callback` couvre ce
 * blocage ET une fermeture de la fenêtre de consentement par l'utilisateur —
 * sans lui, la promesse ne se réglait jamais (revue Task 7, tour 1). */
export function obtenirJetonPickerDrive(clientId) {
  return new Promise((resolve, reject) => {
    const refuse = () => reject(Object.assign(
      new Error('Autorisation Google refusée'), { code: 'drive_autorisation_refusee' }));
    try {
      const client = window.google.accounts.oauth2.initTokenClient({
        client_id: clientId,
        scope: GOOGLE_PICKER_SCOPE,
        callback: (reponse) => {
          if (reponse && reponse.access_token) resolve(reponse.access_token);
          else refuse();
        },
        error_callback: refuse,
      });
      client.requestAccessToken();
    } catch (e) { reject(e); }
  });
}

/** Ouvre le sélecteur Drive ; renvoie les fichiers choisis
 * (`[{id, name, mimeType}]`), ou `[]` si l'utilisateur annule.
 *
 * N'attend PAS `chargerGooglePicker()` avant `obtenirJetonPickerDrive` :
 * l'appelant est censé avoir déjà préchargé les scripts (au montage) pour
 * que le jeton soit demandé sans délai réseau après le clic. Si le
 * chargement n'était pas terminé, `obtenirJetonPickerDrive` échouerait de
 * toute façon (`window.google` non défini) — l'appelant peut alors afficher
 * l'erreur et réessayer un instant plus tard. */
export async function ouvrirPickerDrive(apiKey, clientId) {
  const jeton = await obtenirJetonPickerDrive(clientId);
  return new Promise((resolve, reject) => {
    try {
      const vue = new window.google.picker.DocsView()
        .setIncludeFolders(false)
        .setMimeTypes(GOOGLE_PICKER_MIME_TYPES);
      const picker = new window.google.picker.PickerBuilder()
        .addView(vue)
        .setOAuthToken(jeton)
        .setDeveloperKey(apiKey)
        .setAppId(clientId.split('-')[0])
        .setCallback((donnee) => {
          if (donnee.action === window.google.picker.Action.PICKED) {
            resolve((donnee.docs || []).map((d) => ({ id: d.id, name: d.name, mimeType: d.mimeType })));
          } else if (donnee.action === window.google.picker.Action.CANCEL) {
            resolve([]);
          }
        })
        .build();
      picker.setVisible(true);
    } catch (e) { reject(e); }
  });
}
