/* `GET /version` : l'identifiant du build que ce serveur Next sert en ce
 * moment. Lu par le client (`version.js`) pour détecter qu'un déploiement a eu
 * lieu depuis le chargement de l'onglet. Jamais mis en cache. */
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json(
    { build: process.env.NEXT_PUBLIC_BUILD_ID || "" },
    { headers: { "Cache-Control": "no-store" } },
  );
}
