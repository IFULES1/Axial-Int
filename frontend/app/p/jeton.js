/* Extraction du jeton de partage depuis le dernier segment de l'URL publique
   `/p/<pseudo>/<slug>-<jeton>`.

   Module à part, pur (ni React, ni `window`, ni `fetch`) : c'est la seule
   logique de la page publique qui puisse se tromper silencieusement, et un
   test Node doit pouvoir l'exercer sans monter Next.

   Le jeton est pris sur les 22 DERNIERS caractères, et non « après le dernier
   tiret » : `secrets.token_urlsafe(16)` tire dans l'alphabet base64url, qui
   contient `-`. Un jeton sur huit environ porte donc un tiret, et
   `lastIndexOf('-')` le couperait en deux — le lien rendrait 404 sans qu'on
   comprenne pourquoi, au hasard des titres. La longueur, elle, est fixe. */

/* Miroir de `JETON_LONGUEUR` dans `app/modules/reports/service.py` (= 22, dérivé
   de `JETON_OCTETS = 16`). Les deux constantes doivent rester égales ; côté
   backend, `test_le_jeton_a_la_longueur_exportee`
   (`tests/test_rapports_v2.py`) casse avant le front si `JETON_OCTETS` change. */
export const LONGUEUR_JETON = 22;

// Construit depuis la constante : pas de « 22 » écrit deux fois dans ce fichier.
const MOTIF_JETON = new RegExp(`^[A-Za-z0-9_-]{${LONGUEUR_JETON}}$`);

/** `slug` → jeton, ou `null` si ce segment ne peut pas en porter un. */
export function jetonDuSlug(slug) {
  let s = String(slug == null ? '' : slug);
  try { s = decodeURIComponent(s); } catch (e) { /* segment mal encodé : tel quel */ }
  if (s.length < LONGUEUR_JETON) return null;
  const jeton = s.slice(-LONGUEUR_JETON);
  if (!MOTIF_JETON.test(jeton)) return null;
  // Ce qui précède le jeton est le slug du titre, et le serveur pose toujours
  // un tiret entre les deux. Sans cette vérification, les 22 derniers
  // caractères de n'importe quelle URL passeraient pour un jeton.
  const avant = s.slice(0, -LONGUEUR_JETON);
  if (avant && !avant.endsWith('-')) return null;
  return jeton;
}
