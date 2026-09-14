/* Détection d'une nouvelle version du front.
 *
 * Module pur (testé sous Node) : la logique de comparaison et la cadence des
 * vérifications vivent ici ; App.jsx ne fait qu'afficher le bandeau. */

export const INTERVALLE_VERIFICATION_MS = 10 * 60 * 1000;

/** Vrai quand le serveur sert un build différent de celui de l'onglet.
 *  Deux identifiants vides (dev, serveur muet) ne signalent jamais rien. */
export function versionDifferente(locale, distante) {
  if (!locale || !distante) return false;
  return String(locale) !== String(distante);
}

/**
 * Monte la veille : vérifie au démarrage, à chaque retour de l'onglet au
 * premier plan, et toutes les `intervalleMs`. Appelle `onNouvelle(distante)`
 * UNE fois, puis s'arrête. Retourne une fonction d'arrêt.
 *
 * `lire` : () => Promise<string> (identifiant distant) ; une lecture qui
 * échoue est ignorée (réseau coupé ≠ nouvelle version).
 * `fenetre` : injectable pour les tests (addEventListener, setInterval…).
 */
export function creerVeilleVersion({ locale, lire, onNouvelle,
                                    intervalleMs = INTERVALLE_VERIFICATION_MS,
                                    fenetre = globalThis }) {
  let arretee = false;
  let enCours = false;
  let minuterie = null;

  const verifier = async () => {
    if (arretee || enCours) return;
    enCours = true;
    try {
      const distante = await lire();
      if (!arretee && versionDifferente(locale, distante)) {
        arreter();
        onNouvelle(distante);
      }
    } catch { /* ignoré : on réessaiera au prochain tick */ }
    finally { enCours = false; }
  };
  const surVisibilite = () => {
    if (fenetre.document?.visibilityState === "visible") verifier();
  };
  const arreter = () => {
    if (arretee) return;
    arretee = true;
    if (minuterie !== null) fenetre.clearInterval(minuterie);
    fenetre.document?.removeEventListener?.("visibilitychange", surVisibilite);
  };

  fenetre.document?.addEventListener?.("visibilitychange", surVisibilite);
  minuterie = fenetre.setInterval(verifier, intervalleMs);
  verifier();
  return arreter;
}

/** Lecture par défaut : `GET /version` sur le même hôte que la page. */
export async function lireVersionServie(fetchImpl = globalThis.fetch) {
  const res = await fetchImpl("/version", { cache: "no-store" });
  if (!res.ok) throw new Error(`version: ${res.status}`);
  const corps = await res.json();
  return corps?.build || "";
}
