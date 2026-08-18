/* Gabarit commun des pages légales — lisible, sobre, cohérent avec l'app. */
export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      minHeight: "100vh", background: "#08080e", color: "#d6d6e0",
      fontFamily: "system-ui, -apple-system, sans-serif", lineHeight: 1.65,
    }}>
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "48px 24px 80px" }}>
        <a href="/" style={{ color: "#9b98f5", textDecoration: "none", fontSize: 14 }}>← Axial Intelligence</a>
        <div className="legal-body" style={{ marginTop: 24 }}>{children}</div>
        <hr style={{ border: "none", borderTop: "1px solid #26263a", margin: "48px 0 20px" }} />
        <nav style={{ display: "flex", gap: 18, fontSize: 13 }}>
          <a href="/legal/cgu" style={{ color: "#9b98f5" }}>CGU</a>
          <a href="/legal/confidentialite" style={{ color: "#9b98f5" }}>Confidentialité</a>
          <a href="/legal/mentions" style={{ color: "#9b98f5" }}>Mentions légales</a>
        </nav>
      </div>
      <style>{`
        .legal-body h1 { font-size: 28px; letter-spacing: -0.02em; color: #f2f2f7; margin: 0 0 6px; }
        .legal-body h2 { font-size: 17px; color: #f2f2f7; margin: 32px 0 8px; }
        .legal-body p, .legal-body li { font-size: 14.5px; color: #b9b9c9; }
        .legal-body ul { padding-left: 20px; }
        .legal-body .date { font-size: 12.5px; color: #7a7a8f; }
        .legal-body strong { color: #d6d6e0; }
        .legal-body table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
        .legal-body td, .legal-body th { border: 1px solid #26263a; padding: 8px 10px; text-align: left; color: #b9b9c9; }
      `}</style>
    </div>
  );
}
