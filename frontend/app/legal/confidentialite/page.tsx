export const metadata = { title: "Politique de confidentialité — Axial Intelligence" };

export default function Confidentialite() {
  return (
    <article>
      <h1>Politique de confidentialité</h1>
      <p className="date">Version du 18 août 2026 — conforme RGPD</p>

      <h2>1. Responsable de traitement</h2>
      <p>
        Axial Intelligence (voir <a href="/legal/mentions" style={{ color: "#9b98f5" }}>mentions légales</a>)
        est responsable du traitement des données collectées via app.axial-ia.fr.
        Contact : <strong>sales@axial-ia.fr</strong>.
      </p>

      <h2>2. Données collectées</h2>
      <ul>
        <li><strong>Compte</strong> : email professionnel, nom, mot de passe (haché — jamais stocké en clair).</li>
        <li><strong>Profil entreprise</strong> : nom, site web, positionnement, secteur, stade, marché, concurrents, défi — saisis par vous pour personnaliser les analyses.</li>
        <li><strong>Documents</strong> : fichiers que vous téléversez volontairement (pitch deck, études…), stockés et indexés pour vos seules analyses.</li>
        <li><strong>Usage</strong> : conversations, rapports, consommation de crédits, journaux techniques.</li>
        <li><strong>Paiement</strong> : traité par Stripe ; nous ne voyons ni ne stockons votre numéro de carte.</li>
      </ul>

      <h2>3. Finalités et bases légales</h2>
      <table>
        <thead><tr><th>Finalité</th><th>Base légale</th></tr></thead>
        <tbody>
          <tr><td>Fournir le Service (analyses, veille, rapports personnalisés)</td><td>Exécution du contrat</td></tr>
          <tr><td>Facturation et gestion de l&apos;abonnement</td><td>Exécution du contrat / obligation légale</td></tr>
          <tr><td>Sécurité, prévention de la fraude</td><td>Intérêt légitime</td></tr>
          <tr><td>Emails de veille demandés par vous</td><td>Exécution du contrat</td></tr>
          <tr><td>Amélioration du Service (statistiques d&apos;usage)</td><td>Intérêt légitime</td></tr>
        </tbody>
      </table>

      <h2>4. Ce que nous ne faisons jamais</h2>
      <ul>
        <li>Vos données ne servent <strong>jamais à entraîner des modèles d&apos;IA</strong>, ni pour nous ni pour des tiers.</li>
        <li>Vos données ne sont <strong>jamais vendues</strong> ni partagées à des fins publicitaires.</li>
        <li>Votre mémoire et vos documents ne sont <strong>jamais accessibles à d&apos;autres utilisateurs</strong>.</li>
      </ul>

      <h2>5. Sous-traitants</h2>
      <p>Le Service s&apos;appuie sur des prestataires agissant sur instruction :</p>
      <table>
        <thead><tr><th>Prestataire</th><th>Rôle</th><th>Localisation</th></tr></thead>
        <tbody>
          <tr><td>Supabase</td><td>Base de données et authentification</td><td>Union européenne (région eu-west)</td></tr>
          <tr><td>Hostinger</td><td>Hébergement applicatif</td><td>Union européenne</td></tr>
          <tr><td>Stripe</td><td>Paiements</td><td>UE/États-Unis (clauses contractuelles types)</td></tr>
          <tr><td>Anthropic / Google</td><td>Génération des analyses (IA) — sans conservation d&apos;entraînement</td><td>États-Unis (CCT)</td></tr>
          <tr><td>Cohere</td><td>Recherche sémantique (embeddings/rerank)</td><td>États-Unis/Canada (CCT)</td></tr>
          <tr><td>Resend</td><td>Envoi d&apos;emails transactionnels et de veille</td><td>UE/États-Unis (CCT)</td></tr>
        </tbody>
      </table>

      <h2>6. Durées de conservation</h2>
      <ul>
        <li>Données de compte et contenus : pendant la vie du compte, puis supprimés sous <strong>30 jours</strong> après clôture.</li>
        <li>Données de facturation : 10 ans (obligation comptable).</li>
        <li>Journaux techniques : 12 mois maximum.</li>
      </ul>

      <h2>7. Vos droits</h2>
      <p>
        Conformément au RGPD, vous disposez des droits d&apos;accès, de rectification,
        d&apos;effacement, de portabilité, de limitation et d&apos;opposition. Exercez-les à
        <strong> sales@axial-ia.fr</strong> — réponse sous 30 jours. Vous pouvez
        supprimer vous-même votre profil et vos documents depuis l&apos;application.
        Réclamation possible auprès de la CNIL (cnil.fr).
      </p>

      <h2>8. Sécurité</h2>
      <p>
        Chiffrement en transit (HTTPS/TLS), secrets gérés hors du code, accès
        serveurs par clé uniquement, cloisonnement strict des données par compte,
        surveillance et sauvegardes gérées par nos hébergeurs.
      </p>

      <h2>9. Cookies</h2>
      <p>
        Le Service utilise uniquement le stockage local nécessaire au fonctionnement
        (session, préférences). Pas de cookies publicitaires ni de traceurs tiers.
      </p>
    </article>
  );
}
