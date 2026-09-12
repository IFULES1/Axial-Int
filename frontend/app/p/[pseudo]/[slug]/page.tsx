/* Page publique d'un rapport partagé : `/p/<pseudo>/<slug>-<jeton>` (spec §0).
 *
 * Composant SERVEUR, sans état, sans React client, sans barre d'application :
 * le visiteur n'a pas de compte chez nous, il n'y a rien à piloter. Le rendu
 * se fait au moment de la requête (`cache: 'no-store'`) — un partage révoqué
 * doit rendre 404 tout de suite, pas à l'expiration d'un cache.
 *
 * Le markdown est analysé par `markdown.js`, le MÊME module que l'application
 * (module ES pur, sans React ni `window` : c'est exactement ce pour quoi il a
 * été écrit). Un second parseur aurait fini par rendre le même rapport
 * autrement selon qu'on le lit connecté ou partagé.
 */
import { notFound } from "next/navigation";

import { parserMarkdown } from "../../../_prototype/markdown.js";
import { APP, PageEtat, TEXTES } from "../../etats";
import { jetonDuSlug } from "../../jeton.js";
import "../../partage.css";

// `noindex` : un rapport partagé par lien n'a pas à se retrouver dans un
// moteur de recherche. Le jeton rend l'URL non devinable ; l'indexation la
// rendrait publique pour de bon.
export const metadata = {
  robots: { index: false, follow: false },
  title: "Rapport partagé — Axial Intelligence",
};

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8090";

/* Issue de la lecture : le rapport, « revoque » (404 : lien mort ou jamais
   ouvert) ou « panne » (5xx, réseau, JSON illisible). La distinction compte :
   une panne backend faisait lire « lien introuvable » sur TOUS les liens
   partagés, sans qu'aucune trace ne sépare la panne de la révocation (revue
   Task 5, finding 3). */
type Resultat =
  | { etat: "ok"; rapport: RapportPublic }
  | { etat: "revoque" }
  | { etat: "panne" };

type SourcePublique = {
  title?: string | null;
  url?: string | null;
  domain?: string | null;
  source?: string | null;
};

type VizPublique = {
  empreinte?: string | null;
  statut?: string | null;
  spec?: { series?: { label?: string; value?: number }[]; unit?: string } | null;
};

type RapportPublic = {
  title: string;
  content: string;
  sources: SourcePublique[] | null;
  viz: VizPublique[] | null;
  analysis_type: string;
  created_at: string;
  pseudo: string;
};

async function lireRapport(jeton: string): Promise<Resultat> {
  let res: Response;
  try {
    res = await fetch(`${API}/partage/${encodeURIComponent(jeton)}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch (e) {
    // API injoignable. Tracé côté SERVEUR (console du process Next) : sans
    // cette ligne, une panne backend se lisait « lien introuvable » sans
    // qu'aucun journal ne le dise. Le visiteur, lui, ne voit rien de tout ça.
    console.error("[partage] API injoignable", e);
    return { etat: "panne" };
  }
  if (res.status === 404) return { etat: "revoque" };
  if (!res.ok) {
    // Le jeton n'est PAS journalisé : il tient lieu d'autorisation, un journal
    // d'application n'est pas l'endroit où le laisser traîner.
    console.error(`[partage] API en erreur : HTTP ${res.status}`);
    return { etat: "panne" };
  }
  try {
    return { etat: "ok", rapport: (await res.json()) as RapportPublic };
  } catch (e) {
    console.error("[partage] réponse illisible", e);
    return { etat: "panne" };
  }
}



/* ---------- rendu des nœuds inline ---------- */
/* Formes produites par `markdown.js` : text, strong, em, code, link, cite.
   Un lien sort en `rel="nofollow noopener noreferrer"` : ces URL viennent du
   modèle, pas de nous, et la page est publique. */
function Inline({ nodes }: { nodes: any[] }) {
  return (
    <>
      {(nodes || []).map((n: any, i: number) => {
        if (!n) return null;
        if (n.type === "text") return <span key={i}>{n.text}</span>;
        if (n.type === "strong") return <strong key={i}><Inline nodes={n.children} /></strong>;
        if (n.type === "em") return <em key={i}><Inline nodes={n.children} /></em>;
        if (n.type === "code") return <code key={i}>{n.text}</code>;
        if (n.type === "link") {
          return (
            <a key={i} href={n.href} target="_blank" rel="nofollow noopener noreferrer">
              <Inline nodes={n.children} />
            </a>
          );
        }
        if (n.type === "cite") {
          // Renvoi vers la liste des sources, en bas de page.
          return (
            <a key={i} className="rp-cite" href={`#rp-src-${n.n}`}>[{n.n}]</a>
          );
        }
        return null;
      })}
    </>
  );
}

/* Un graphique : l'image SVG servie par l'API avec le jeton de partage
   (`GET /viz/{empreinte}.svg?p=<jeton>`, autorisé par Task 3 pour les
   empreintes de CE rapport uniquement). Si le rendu n'existe pas, on retombe
   sur les données du bloc en tableau — perdre les chiffres serait pire que
   perdre la courbe. */
function Graphique({ viz, jeton }: { viz: VizPublique | undefined; jeton: string }) {
  if (viz && viz.empreinte && viz.statut === "ok") {
    return (
      <figure className="rp-viz">
        {/* `<img>` et non `next/image` : l'image est un SVG servi par l'API
            avec un paramètre d'autorisation, elle n'a rien à faire dans
            l'optimiseur d'images de Next. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`${API}/viz/${encodeURIComponent(viz.empreinte)}.svg?p=${encodeURIComponent(jeton)}`}
          alt=""
          loading="lazy"
        />
      </figure>
    );
  }
  const series = (viz && viz.spec && viz.spec.series) || null;
  if (!series || !series.length) return null;
  return (
    <div className="rp-table-wrap">
      <table>
        <thead>
          <tr><th /><th>{(viz && viz.spec && viz.spec.unit) || ""}</th></tr>
        </thead>
        <tbody>
          {series.map((p, i) => (
            <tr key={i}><td>{p.label}</td><td>{String(p.value)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------- rendu des blocs ---------- */
function Blocs({ blocks, viz, jeton }: { blocks: any[]; viz: VizPublique[] | null; jeton: string }) {
  // Rang du bloc de visualisation : le serveur numérote les `viz` dans l'ordre
  // d'apparition dans le markdown, ce compteur suit le même ordre.
  let rangViz = 0;
  return (
    <>
      {(blocks || []).map((b: any, i: number) => {
        if (!b) return null;
        if (b.type === "heading") {
          const Tag = (b.level === 1 ? "h1" : b.level === 2 ? "h2" : "h3") as "h1" | "h2" | "h3";
          return <Tag key={i}><Inline nodes={b.inline} /></Tag>;
        }
        if (b.type === "paragraph") return <p key={i}><Inline nodes={b.inline} /></p>;
        if (b.type === "list") {
          const Tag = (b.ordered ? "ol" : "ul") as "ol" | "ul";
          return (
            <Tag key={i}>
              {(b.items || []).map((it: any, j: number) => (
                <li key={j}>
                  <Inline nodes={it.inline} />
                  {it.children && it.children.length ? (
                    <ul>
                      {it.children.map((c: any, k: number) => (
                        <li key={k}><Inline nodes={c.inline} /></li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </Tag>
          );
        }
        if (b.type === "table") {
          return (
            <div className="rp-table-wrap" key={i}>
              <table>
                <thead>
                  <tr>{(b.header || []).map((c: any, j: number) => <th key={j}><Inline nodes={c} /></th>)}</tr>
                </thead>
                <tbody>
                  {(b.rows || []).map((r: any[], j: number) => (
                    <tr key={j}>{r.map((c: any, k: number) => <td key={k}><Inline nodes={c} /></td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (b.type === "viz") {
          const courant = (viz || [])[rangViz];
          rangViz += 1;
          return <Graphique key={i} viz={courant} jeton={jeton} />;
        }
        if (b.type === "code") return <pre key={i}><code>{b.code}</code></pre>;
        if (b.type === "quote") {
          return (
            <blockquote key={i}>
              <Blocs blocks={b.blocks} viz={null} jeton={jeton} />
            </blockquote>
          );
        }
        if (b.type === "hr") return <hr key={i} />;
        return null;
      })}
    </>
  );
}

function dateLisible(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(TEXTES.locale, { day: "numeric", month: "long", year: "numeric" });
}

export default async function PagePartage(
  { params }: { params: { pseudo: string; slug: string } },
) {
  const jeton = jetonDuSlug(params.slug);
  // Segment qui ne peut pas porter de jeton : c'est une URL inventée, donc un
  // vrai 404 de routage (et non l'écran « plus partagé »).
  if (!jeton) notFound();

  const lu = await lireRapport(jeton);
  if (lu.etat === "panne") {
    return <PageEtat titre={TEXTES.panneTitre} corps={TEXTES.panneCorps} />;
  }
  /* Lien révoqué : `notFound()` rend le `not-found.tsx` de CE segment — la
     page « Ce rapport n'est plus partagé », avec un vrai HTTP 404. Un lien
     mort qui répondrait 200 tromperait robots et supervision. */
  if (lu.etat === "revoque") notFound();
  const rapport = lu.rapport;

  const blocks = parserMarkdown(rapport.content || "");
  const sources = rapport.sources || [];
  // Le pseudo affiché est celui que le SERVEUR a figé au moment du partage, pas
  // le segment d'URL : celui-ci est libre (l'URL peut être retapée à la main)
  // et afficherait n'importe quel nom au-dessus du rapport de quelqu'un.
  const pseudo = rapport.pseudo || params.pseudo;

  return (
    <div className="partage-page">
      <div className="rp-corps">
        <header className="rp-entete">
          <span>{TEXTES.partagePar} {pseudo}</span>
          <span>·</span>
          <a href={APP}>{TEXTES.marque}</a>
        </header>

        <h1 className="rp-titre">{rapport.title}</h1>
        <p className="rp-meta">
          {dateLisible(rapport.created_at)}
          {sources.length ? ` · ${sources.length} ${TEXTES.sourcesSuffixe}` : ""}
        </p>

        <article className="rp-doc">
          <Blocs blocks={blocks} viz={rapport.viz || null} jeton={jeton} />
        </article>

        {sources.length > 0 && (
          <section className="rp-sources">
            <div className="rp-sources-titre">{TEXTES.sources}</div>
            {sources.map((s, i) => (
              <div className="rp-source" key={i} id={`rp-src-${i + 1}`}>
                <span className="rp-num">[{i + 1}]</span>
                {s.url ? (
                  <a href={s.url} target="_blank" rel="nofollow noopener noreferrer">
                    {s.title || s.url}
                  </a>
                ) : (
                  <span>{s.title || ""}</span>
                )}
                {s.domain ? <span className="rp-domaine">· {s.domain}</span> : null}
              </div>
            ))}
          </section>
        )}

        <footer className="rp-pied">
          {TEXTES.piedAvant} <a href={APP}>{TEXTES.marque}</a> {TEXTES.piedApres}
        </footer>
      </div>
    </div>
  );
}
