/* Le 404 de la route de partage : lien révoqué, jeton illisible, ou rapport
   qui n'a jamais été partagé. Une page à part — et non le `not-found` global
   de l'application — parce que le visiteur d'un lien mort n'a pas besoin d'une
   barre d'application ni d'un « page introuvable » générique : il a besoin de
   savoir que le lien ne vaut plus rien et qu'il peut en redemander un.

   C'est un `not-found.tsx` de segment, donc le `notFound()` de la page rend
   bien un HTTP 404 : un lien mort qui répondrait 200 tromperait les robots et
   toute supervision (le `noindex` de la page ne dit rien du code de statut). */
import { PageEtat, TEXTES } from "../../etats";
import "../../partage.css";

export const metadata = {
  robots: { index: false, follow: false },
  title: "Lien expiré — Axial Intelligence",
};

export default function Introuvable() {
  return <PageEtat titre={TEXTES.revoqueTitre} corps={TEXTES.revoqueCorps} />;
}
