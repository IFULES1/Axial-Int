import type { MetadataRoute } from "next";

/* Pages publiques de l'app : la landing et les pages légales. Tout le reste
 * est derrière l'authentification. */
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://app.axial-ia.fr";
  const maj = new Date("2026-09-18");
  return [
    { url: `${base}/`, lastModified: maj, changeFrequency: "weekly", priority: 1 },
    { url: `${base}/legal/cgu`, lastModified: maj, changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/legal/confidentialite`, lastModified: maj, changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/legal/mentions`, lastModified: maj, changeFrequency: "yearly", priority: 0.3 },
  ];
}
