import { execSync } from "node:child_process";

/* Identifiant de build calculé UNE fois au chargement de la config, partagé
 * entre le `buildId` Next et la variable publique lue par le client. Un onglet
 * ouvert avant un déploiement compare son identifiant (figé dans son bundle)
 * à celui que sert `GET /version` (le build en cours) : s'ils diffèrent, il
 * propose de recharger. Cause des « boutons inopérants » et de « l'historique
 * disparu » constatés le 13/09 : d'anciens bundles parlant à une API neuve. */
function identifiantDeBuild() {
  let sha = "";
  try {
    sha = execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] })
      .toString().trim();
  } catch { /* hors dépôt git (serveur de prod) : l'horodatage suffit */ }
  return `${Date.now().toString(36)}${sha ? "-" + sha : ""}`;
}
const BUILD_ID = identifiantDeBuild();

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  generateBuildId: () => BUILD_ID,
  env: { NEXT_PUBLIC_BUILD_ID: BUILD_ID },
};

export default nextConfig;
