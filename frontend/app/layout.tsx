import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://app.axial-ia.fr"),
  title: "Axial Intelligence",
  description: "Le copilote stratégique des décisions de fondateur.",
  // Vérification Search Console « préfixe d'URL », si un jour la propriété
  // de domaine (enregistrement TXT sur axial-ia.fr) ne suffit pas : poser
  // NEXT_PUBLIC_GSC_VERIFICATION dans frontend/.env.local puis rebâtir.
  ...(process.env.NEXT_PUBLIC_GSC_VERIFICATION
    ? { verification: { google: process.env.NEXT_PUBLIC_GSC_VERIFICATION } }
    : {}),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
