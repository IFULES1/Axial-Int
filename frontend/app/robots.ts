import type { MetadataRoute } from "next";

/* Suivi du trafic (18/09) : ce que Google et Bing peuvent explorer sur l'app.
 * Les pages de partage `/p/…` portent un jeton non devinable et du contenu
 * privé de l'utilisateur : hors index. `/api/` et `/version` sont techniques. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: ["/", "/legal/"], disallow: ["/api/", "/p/", "/version"] }],
    sitemap: "https://app.axial-ia.fr/sitemap.xml",
    host: "https://app.axial-ia.fr",
  };
}
