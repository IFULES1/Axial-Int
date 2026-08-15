import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Axial Intelligence",
  description: "Le copilote stratégique des décisions de fondateur.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
