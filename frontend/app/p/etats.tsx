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
  // Singulier ET pluriel : le compteur affichait « 1 sources » (revue finale,
  // F15). Une fonction plutôt que deux clés à recoller sur place — le choix se
  // fait ici, avec les textes, pas dans le JSX.
  sourcesSuffixe: "sources",
  sourcesSuffixeUn: "source",
  piedAvant: "Rapport produit par",
  piedApres: "— le copilote stratégique des décisions de fondateur.",
  /* Écran 404 (revue finale, F15). Trois incohérences corrigées :
     le `<title>` disait « Lien expiré » quand le corps disait « révoqué » ;
     la phrase qui renvoyait vers l'auteur n'avait aucun sens sur un lien qui
     n'a jamais existé ; et le texte prétendait trancher entre les deux.

     Il ne PEUT pas trancher : le backend rend 404 pour un jeton révoqué comme
     pour un jeton inventé, délibérément — répondre différemment dirait à qui
     essaie des jetons au hasard lesquels ont existé. Le texte dit donc
     l'ACTION possible (redemander un lien), pas un diagnostic qu'on n'a pas.
     Le `<title>` de `not-found.tsx` reprend `revoqueTitre` mot pour mot. */
  revoqueTitre: "Ce lien ne mène à aucun rapport",
  revoqueCorps:
    "Le lien a été révoqué par son auteur, ou l'adresse est incomplète. "
    + "Vérifiez l'adresse copiée, ou redemandez un lien à la personne qui vous "
    + "l'a transmis.",
  panneTitre: "Service indisponible",
  panneCorps:
    "Nous n'arrivons pas à afficher ce rapport pour le moment. "
    + "Réessayez dans quelques minutes.",
  retour: "Découvrir Axial Intelligence",
  // Locale des dates : figée avec les textes, pour la même raison.
  locale: "fr-FR",
};

/** « 1 source » / « 12 sources ». Le compteur rendait « 1 sources ». */
export function compterSources(n: number): string {
  return `${n} ${n > 1 ? TEXTES.sourcesSuffixe : TEXTES.sourcesSuffixeUn}`;
}

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
