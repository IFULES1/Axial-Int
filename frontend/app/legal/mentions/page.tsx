export const metadata = { title: "Mentions légales — Axial Intelligence" };

export default function Mentions() {
  return (
    <article>
      <h1>Mentions légales</h1>
      <p className="date">Version du 18 août 2026</p>

      <h2>Éditeur</h2>
      <p>
        Axial Intelligence<br />
        [À COMPLÉTER : forme juridique, capital social]<br />
        [À COMPLÉTER : adresse du siège]<br />
        [À COMPLÉTER : n° SIREN/RCS]<br />
        Directeur de la publication : [À COMPLÉTER]<br />
        Contact : sales@axial-ia.fr
      </p>

      <h2>Hébergement</h2>
      <p>
        Hostinger International Ltd — 61 Lordou Vironos Street, 6023 Larnaca, Chypre
        (serveurs situés dans l&apos;Union européenne).<br />
        Base de données et authentification : Supabase Inc. (région UE).
      </p>

      <h2>Propriété intellectuelle</h2>
      <p>
        L&apos;ensemble du site (marque, interface, textes, code) est protégé par le
        droit de la propriété intellectuelle. Toute reproduction non autorisée est
        interdite.
      </p>

      <h2>Données personnelles</h2>
      <p>
        Voir la <a href="/legal/confidentialite" style={{ color: "#9b98f5" }}>Politique de confidentialité</a>.
      </p>
    </article>
  );
}
