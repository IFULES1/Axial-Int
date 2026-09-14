/* `GET /version` : l'identifiant du build que ce serveur Next sert en ce
 * moment. Lu par le client (`version.js`) pour détecter qu'un déploiement a eu
 * lieu depuis le chargement de l'onglet. Jamais mis en cache.
 *
 * La source de vérité est le fichier `.next/BUILD_ID` écrit par `next build`
 * (même valeur que celle figée dans le bundle client via `env`). Surtout PAS
 * `process.env.NEXT_PUBLIC_BUILD_ID` côté serveur : `next start` ré-évalue
 * `next.config.mjs` au démarrage et recalculerait un identifiant différent de
 * celui du bundle — le bandeau s'afficherait alors à tout le monde, toujours
 * (constaté au premier déploiement, 14/09). En `next dev`, le fichier n'existe
 * pas : on retombe sur la variable, calculée une seule fois par le processus. */
import { readFileSync } from "node:fs";
import { join } from "node:path";

export const dynamic = "force-dynamic";

function identifiantServi(): string {
  try {
    return readFileSync(join(process.cwd(), ".next", "BUILD_ID"), "utf8").trim();
  } catch {
    return process.env.NEXT_PUBLIC_BUILD_ID || "";
  }
}

export function GET() {
  return Response.json(
    { build: identifiantServi() },
    { headers: { "Cache-Control": "no-store" } },
  );
}
