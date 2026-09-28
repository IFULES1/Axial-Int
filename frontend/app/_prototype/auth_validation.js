/* Validation explicite du formulaire de connexion / inscription (28/09).
 *
 * Avant : `required`, `type="email"` et `minLength` laissaient le navigateur
 * refuser l'envoi avec une bulle native, discrète ou invisible sur téléphone.
 * Un visiteur est resté dix minutes sur l'écran sans qu'aucune requête ne
 * parte. Ici la règle est la même, mais l'écran l'affiche lui-même. */

export const MOT_DE_PASSE_MIN = 8;

// Un « @ » entouré de texte et un point dans le domaine : assez strict pour
// attraper une faute de frappe, assez souple pour ne pas refuser une adresse
// valide inhabituelle (le serveur revalide de toute façon).
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** Retourne le message d'erreur (français) ou null si tout est envoyable. */
export function validerIdentifiants({ mode, email, pwd }) {
  const e = (email || '').trim();
  if (!e) return "Renseignez votre adresse email.";
  if (!EMAIL.test(e)) return "Cette adresse email semble incomplète (ex. vous@entreprise.com).";
  if (!pwd) return "Renseignez votre mot de passe.";
  if (mode === 'signup' && pwd.length < MOT_DE_PASSE_MIN) return `Le mot de passe doit faire au moins ${MOT_DE_PASSE_MIN} caractères.`;
  return null;
}

/** Email normalisé pour l'envoi : espaces retirés, casse abaissée. */
export function emailNormalise(email) {
  return (email || '').trim().toLowerCase();
}
