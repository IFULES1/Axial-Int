/* Textes et écrans d'état de la page publique de partage (`/p/…`).
 *
 * Module à part parce que DEUX entrées en ont besoin : la page elle-même
 * (service injoignable) et le `not-found.tsx` de la route (lien révoqué, qui
 * doit répondre un vrai HTTP 404 et non un 200 poli).
 *
 * La page publique est en FRANÇAIS FIGÉ et n'appelle pas `t()` : c'est
 * l'arbitrage de la spec §0 — le destinataire d'un lien n'a pas de compte chez
 * nous, donc pas de langue. Tout regrouper ici rend l'arbitrage visible, et le
 * jour où le partage devra suivre la langue du rapport il n'y a qu'un objet à
 * indexer par langue (revue Task 5, finding 5).
 */
export const APP = "https://app.axial-ia.fr";

export const TEXTES = {
  partagePar: "Rapport partagé par",
  marque: "Axial Intelligence",
  sources: "Sources",
  sourcesSuffixe: "sources",
  piedAvant: "Rapport produit par",
  piedApres: "— le copilote stratégique des décisions de fondateur.",
  revoqueTitre: "Ce rapport n'est plus partagé",
  revoqueCorps:
    "Le lien a été révoqué par son auteur, ou il n'a jamais existé. "
    + "Demandez-lui un nouveau lien.",
  panneTitre: "Service indisponible",
  panneCorps:
    "Nous n'arrivons pas à afficher ce rapport pour le moment. "
    + "Réessayez dans quelques minutes.",
  retour: "Découvrir Axial Intelligence",
  // Locale des dates : figée avec les textes, pour la même raison.
  locale: "fr-FR",
};

/* Écran d'état : lien révoqué ou service en panne. Aucun détail technique —
   ni code HTTP, ni message d'exception, ni jeton : le visiteur n'a rien à
   diagnostiquer, et le jeton tient lieu d'autorisation. */
export function PageEtat({ titre, corps }: { titre: string; corps: string }) {
  return (
    <div className="partage-page">
      <div className="rp-etat">
        <h1 className="rp-etat-titre">{titre}</h1>
        <p>{corps}</p>
        <a href={APP}>{TEXTES.retour}</a>
      </div>
    </div>
  );
}
