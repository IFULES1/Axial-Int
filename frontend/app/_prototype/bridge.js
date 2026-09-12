"use client";
// API bridge between the prototype UI and the Axial backend.
// Keeps the exact prototype code intact; screens call these helpers instead of
// their mock stubs, one seam at a time.

export const AX_API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8090";
const TOKEN_KEY = "axial_token";
const REFRESH_KEY = "axial_refresh";

export function axSetToken(t, refresh) {
  try {
    localStorage.setItem(TOKEN_KEY, t);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  } catch (e) {}
}
export function axGetToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
}
export function axClearToken() {
  try { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(REFRESH_KEY); } catch (e) {}
}

// Les access tokens expirent (~1h). Sur un 401, on échange le refresh token
// contre une nouvelle paire puis on rejoue la requête UNE fois — fini les
// échecs silencieux (upload, messages, mémoire) au bout d'une heure.
let _refreshing = null;
async function tryRefresh() {
  if (_refreshing) return _refreshing;  // une seule tentative simultanée
  let rt = null;
  try { rt = localStorage.getItem(REFRESH_KEY); } catch (e) {}
  if (!rt) return Promise.resolve(false);
  _refreshing = (async () => {
    try {
      const res = await fetch(AX_API + "/auth/refresh", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
      // N'effacer les jetons QUE sur un refus avéré du refresh token. Un 502
      // pendant un redémarrage ou un 500 passager laissait l'utilisateur
      // dehors pour de bon, alors que ses jetons étaient encore valides.
      if (res.status === 401 || res.status === 400) { axClearToken(); return false; }
      if (!res.ok) return false;
      const d = await res.json();
      axSetToken(d.access_token, d.refresh_token);
      return true;
    } catch (e) { return false; }
    finally { setTimeout(() => { _refreshing = null; }, 0); }
  })();
  return _refreshing;
}

/** Clé d'idempotence : le backend rejoue le même tour au lieu de re-facturer.
 * `crypto.randomUUID` manque sur les contextes non sécurisés (http://<ip>) et
 * les navigateurs anciens — un repli est obligatoire, sinon « Réessayer »
 * partirait sans clé et paierait deux fois. */
export function nouvelleCleIdempotence() {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  } catch (e) {}
  const r = () => Math.random().toString(16).slice(2, 10);
  return `${r()}-${r()}-${r()}-${r()}`;
}

/** Lit le corps d'erreur d'une réponse HTTP dans les DEUX formes rencontrées :
 * l'enveloppe maison `{error:{code,message}}` (app/errors.py) et le `detail`
 * de FastAPI. Sans le premier cas, `insufficient_credits` et
 * `message_trop_long` arrivaient au front sans code : impossible de les nommer. */
async function erreurDepuisReponse(res, msgDefaut, codeDefaut) {
  let msg = msgDefaut || res.statusText, code;
  try {
    const d = await res.json();
    msg = d.error?.message || d.detail?.message || d.detail || d.message || msg;
    code = d.error?.code || d.detail?.code || d.code;
  } catch (e) {}
  const err = new Error(msg);
  err.status = res.status;
  err.code = code || codeDefaut;
  return err;
}

export async function axFetch(path, { method = "GET", body, auth = true, headers: extra, _retried = false } = {}) {
  const headers = { "Content-Type": "application/json", ...(extra || {}) };
  const tok = auth ? axGetToken() : null;
  if (tok) headers["Authorization"] = "Bearer " + tok;
  const res = await fetch(AX_API + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  // 401 ET 403 : FastAPI répond 403 quand l'en-tête Authorization est absent
  // ou malformé, alors que c'est exactement le cas où il faut réessayer.
  if ((res.status === 401 || res.status === 403) && auth && !_retried
      && path !== "/auth/refresh") {
    const ok = await tryRefresh();
    if (ok) return axFetch(path, { method, body, auth, headers: extra, _retried: true });
    // Rafraîchissement refusé : la session est bel et bien terminée. Le
    // marquer explicitement, parce que le seul code HTTP ne suffit pas —
    // FastAPI rend 403 (et non 401) quand l'en-tête manque, et `decrireErreur`
    // conclurait « réessayer » là où il faut renvoyer vers la connexion.
    throw await erreurDepuisReponse(res, "Session expirée.", "refresh_invalid");
  }
  if (!res.ok) throw await erreurDepuisReponse(res);
  if (res.status === 204) return null;
  return res.json();
}

// --- auth ---
export async function axRegister(email, password, full_name) {
  const r = await axFetch("/auth/register", {
    method: "POST", auth: false,
    body: { email, password, full_name: full_name || null },
  });
  axSetToken(r.access_token, r.refresh_token);
  return r.user;
}
export async function axLogin(email, password) {
  const r = await axFetch("/auth/login", {
    method: "POST", auth: false, body: { email, password },
  });
  axSetToken(r.access_token, r.refresh_token);
  return r.user;
}
/** Demander un lien de réinitialisation (réponse identique si l'adresse est inconnue). */
export async function axForgotPassword(email) {
  return axFetch("/auth/forgot-password", { method: "POST", auth: false, body: { email } });
}
/** Appliquer un nouveau mot de passe via le jeton reçu par email, puis connecter. */
export async function axResetPassword(token, password) {
  const r = await axFetch("/auth/reset-password", {
    method: "POST", auth: false, body: { token, password },
  });
  axSetToken(r.access_token, r.refresh_token);
  return r.user;
}
export async function axMe() {
  return axFetch("/auth/me");
}

// --- memory / onboarding ---
export async function axSaveProfile(profile) {
  return axFetch("/memory/profile", { method: "PUT", body: profile });
}
export async function axGetProfile() {
  return axFetch("/memory/profile");
}

// --- billing ---
export async function axBalance() {
  return axFetch("/billing/balance");
}
export async function axPlans() {
  return axFetch("/billing/plans", { auth: false });
}
/** Start a Stripe checkout for a credit pack; returns { checkout_url }. */
export async function axCheckout(pack) {
  const base = (typeof window !== "undefined" && window.location) ? window.location.origin : "";
  return axFetch("/billing/checkout", {
    method: "POST",
    body: { pack, success_url: base + "/?paid=1", cancel_url: base + "/" },
  });
}
/** Start a recurring monthly subscription checkout; returns { checkout_url }.
 * trial=true (onboarding step 4): card collected now, first debit after 14 days. */
export async function axSubscribe(plan, trial = false) {
  const base = (typeof window !== "undefined" && window.location) ? window.location.origin : "";
  return axFetch("/billing/subscribe", {
    method: "POST",
    body: {
      plan, trial,
      success_url: base + (trial ? "/?onb=done" : "/?subscribed=1"),
      cancel_url: base + (trial ? "/?onb=cancel" : "/"),
    },
  });
}
/** Onboarding: extract {company_name, positioning, sector, website} from a site. */
export async function axPrefill(url) {
  return axFetch("/memory/prefill", { method: "POST", body: { url } });
}
/** Enregistre la langue de production côté serveur (rapports, veilles, réponses). */
export async function axSetLanguage(language) {
  return axFetch("/memory/language", { method: "PUT", body: { language } });
}
/** Email notification preferences. */
export async function axGetNotifPrefs() { return axFetch("/memory/notifications"); }
export async function axSetNotifPrefs(prefs) {
  return axFetch("/memory/notifications", { method: "PUT", body: prefs });
}
/** Current subscription mirror (plan, status, next debit date). */
export async function axSubscription() {
  return axFetch("/billing/subscription");
}
/** Credit ledger (grants + debits, newest first). */
export async function axCreditHistory() {
  return axFetch("/billing/history");
}
/** Stripe invoices with direct download links. */
export async function axInvoices() {
  return axFetch("/billing/invoices");
}
/** Stripe customer portal (manage card, cancel, invoices). */
export async function axPortal() {
  const base = (typeof window !== "undefined" && window.location) ? window.location.origin : "";
  return axFetch("/billing/portal", { method: "POST", body: { return_url: base + "/" } });
}

// --- chat / conversations (Workspace) ---

/** Lecture d'un flux SSE, partagée par le chat et les rapports.
 *
 * Découpe les trames sur la ligne vide, extrait la ligne `data:`, transmet
 * CHAQUE événement à `onEvent` sans le filtrer (le front décide quoi en
 * faire : étapes, avertissements, deltas) et renvoie le `data` du `done`
 * final. `messageInterrompu` distingue « le serveur a coupé avant le done »
 * d'un flux normal.
 */
export async function lireFluxSSE(res, onEvent, messageInterrompu = "Réponse interrompue.") {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", final = null;
  // `finally` couvre TOUTES les sorties (fin normale, `evt.error`, flux coupé
  // sans `done`) : sans ça la connexion restait retenue jusqu'au ramasse-miettes.
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      for (const frame of frames) {
        const line = frame.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;
        let evt;
        try { evt = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }
        if (onEvent) onEvent(evt);
        if (evt.done) {
          if (evt.error) { const e = new Error(evt.error); e.code = evt.code; throw e; }
          final = evt.data || null;
        }
      }
    }
    if (!final) {
      // Le flux s'est fermé avant son `done` : panne réseau, nommée par
      // code — pas par ce texte, que `decrireErreur` ne doit pas connaître
      // par cœur (il change de langue et de formulation).
      const e = new Error(messageInterrompu);
      e.code = "reseau";
      throw e;
    }
    return final;
  } finally {
    reader.cancel().catch(() => {});
  }
}

/** Ouvre une route SSE authentifiée et la lit avec `lireFluxSSE`.
 *
 * - rejoue UNE fois après rafraîchissement du jeton sur 401/403 ;
 * - `X-Idempotency-Key` : sur un « Réessayer », la MÊME clé fait rejouer le
 *   tour côté serveur au lieu de le refacturer ;
 * - un refus 4xx ne se replie PAS sur la route bloquante : rejouer un 402 ou
 *   un 413 ne ferait qu'ajouter un aller-retour avant la même erreur. Seule
 *   une indisponibilité du flux (5xx, corps absent) lève
 *   `stream_unavailable`, que l'appelant peut replier.
 */
async function ouvrirFluxSSE(path, { body, onEvent, signal, idempotencyKey,
                                     messageInterrompu } = {}) {
  const run = async (retried) => {
    const tok = axGetToken();
    let res;
    try {
      res = await fetch(AX_API + path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(tok ? { Authorization: "Bearer " + tok } : {}),
          ...(idempotencyKey ? { "X-Idempotency-Key": idempotencyKey } : {}),
        },
        body: JSON.stringify(body || {}),
        signal,
      });
    } catch (err) {
      // Aucune réponse du tout (réseau coupé) : `fetch` lève un `TypeError`.
      // Nommé par code plutôt que laissé tel quel, pour que `decrireErreur`
      // n'ait pas à connaître ce texte par cœur.
      const e = new Error("reseau");
      e.code = "reseau";
      throw e;
    }
    // 401 ou 403 : même règle que dans axFetch — FastAPI répond 403 quand
    // l'en-tête Authorization manque, ce qui est précisément le cas à réessayer.
    if ((res.status === 401 || res.status === 403) && !retried) {
      const ok = await tryRefresh();
      if (ok) {
        // Ce premier corps de réponse ne sera jamais lu : le libérer, sinon
        // la connexion reste retenue jusqu'au ramasse-miettes.
        if (res.body) res.body.cancel().catch(() => {});
        return run(true);
      }
      throw await erreurDepuisReponse(res, "Session expirée.", "refresh_invalid");
    }
    if (res.status >= 400 && res.status < 500) throw await erreurDepuisReponse(res);
    if (!res.ok || !res.body) {
      const e = new Error("stream_unavailable");
      e.code = "stream_unavailable";
      e.status = res.status;
      throw e;
    }
    return lireFluxSSE(res, onEvent, messageInterrompu);
  };
  return run(false);
}

// --- projets (dossiers) ---
export async function axProjets(inclureArchives = false) {
  return axFetch(`/intelligence/projects?inclure_archives=${inclureArchives ? "true" : "false"}`);
}
export async function axCreerProjet(nom) {
  return axFetch("/intelligence/projects", { method: "POST", body: { name: nom } });
}
export async function axRenommerProjet(id, nom) {
  return axFetch(`/intelligence/projects/${id}`, { method: "PATCH", body: { name: nom } });
}
export async function axArchiverProjet(id, archive = true) {
  return axFetch(`/intelligence/projects/${id}`, { method: "PATCH", body: { archived: !!archive } });
}
export async function axSupprimerProjet(id) {
  return axFetch(`/intelligence/projects/${id}`, { method: "DELETE" });
}

/** Dossier d'accueil des conversations sans dossier choisi.
 * Remplace l'ancien `ensureConversation` : plus d'état module mutable, plus de
 * création implicite de conversation — seulement le dossier « Général ». */
export async function axProjetParDefaut() {
  const projets = await axProjets();
  if (projets.length) return projets[0].id;
  const cree = await axCreerProjet("Général");
  return cree.id;
}

// --- conversations ---
/** Crée une conversation vide dans un dossier (« Général » par défaut). */
export async function axCreateConversation(projectId, titre) {
  const pid = projectId || (await axProjetParDefaut());
  const c = await axFetch(`/intelligence/projects/${pid}/conversations`, {
    method: "POST", body: { title: titre || null },
  });
  return c.id;
}
/** List the user's conversations across ALL their projects.
 * Ne lire que `projects[0]` cachait tout l'historique logé dans un projet
 * plus ancien — ce qui arrive dès que deux appels concurrents créent chacun
 * leur dossier au premier chargement. */
export async function axListConversations({ inclureArchivees = false } = {}) {
  const projects = await axProjets();
  if (!projects.length) return [];
  const listes = await Promise.all(
    projects.map((p) => axFetch(
      `/intelligence/projects/${p.id}/conversations?inclure_archivees=${inclureArchivees ? "true" : "false"}`,
    ).catch(() => [])),
  );
  return listes.flat().sort((a, b) =>
    String(b.last_message_at || "").localeCompare(String(a.last_message_at || "")));
}
export async function axRenommerConversation(id, titre) {
  return axFetch(`/intelligence/conversations/${id}`, { method: "PATCH", body: { title: titre } });
}
export async function axSupprimerConversation(id) {
  return axFetch(`/intelligence/conversations/${id}`, { method: "DELETE" });
}
export async function axEpinglerConversation(id, epingle = true) {
  return axFetch(`/intelligence/conversations/${id}`, { method: "PATCH", body: { pinned: !!epingle } });
}
export async function axArchiverConversation(id, archive = true) {
  return axFetch(`/intelligence/conversations/${id}`, { method: "PATCH", body: { archived: !!archive } });
}
export async function axDeplacerConversation(id, projectId) {
  return axFetch(`/intelligence/conversations/${id}`, { method: "PATCH", body: { project_id: projectId } });
}
/** Recherche plein texte (titre + contenu des messages), 3 caractères minimum. */
export async function axRechercherConversations(q) {
  return axFetch(`/intelligence/conversations/search?q=${encodeURIComponent(q || "")}`);
}
/** Total du fil : crédits, tokens (et coût € pour les admins). */
export async function axCoutConversation(cid) {
  return axFetch(`/intelligence/conversations/${cid}/cout`);
}
/** Fenêtre paginée de messages → `{ items, has_more }`.
 * `before` = identifiant du plus ancien message déjà affiché. */
export async function axMessagesPage(cid, { limit = 50, before } = {}) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (before) q.set("before", before);
  return axFetch(`/intelligence/conversations/${cid}/messages?${q.toString()}`);
}

// --- envoi d'un message ---
/** Documents mis en file par le composer, joints à CE message. */
function documentsEnAttente() {
  const pending = (typeof window !== "undefined" && window.AXIAL_PENDING_DOCS) || [];
  return pending.map((d) => d.id);
}
function viderDocumentsEnAttente() {
  if (typeof window === "undefined") return;
  window.AXIAL_PENDING_DOCS = [];
  try { window.dispatchEvent(new Event("axial-pending-docs")); } catch (e) {}
}
function modeAgent() {
  try { return localStorage.getItem("axial_agent_mode") || "auto"; } catch (e) { return "auto"; }
}

/** Send a chat message into a SPECIFIC backend conversation (route bloquante).
 * Sert de repli quand le flux n'est pas disponible. */
export async function axChatIn(cid, text, { idempotencyKey } = {}) {
  const document_ids = documentsEnAttente();
  const r = await axFetch(`/intelligence/conversations/${cid}/messages`, {
    method: "POST",
    body: { content: text, agent: modeAgent(), document_ids: document_ids.length ? document_ids : null },
    headers: idempotencyKey ? { "X-Idempotency-Key": idempotencyKey } : undefined,
  });
  viderDocumentsEnAttente();
  return r;
}

/** Streamed chat answer : `onEvent` reçoit chaque événement du flux
 * (`etape`, `avertissement`, `sources`, `delta`, `done`) tel quel.
 * Renvoie le message persisté final. Repli sur la route bloquante quand le
 * flux ne s'ouvre pas. */
export async function axStreamChatIn(cid, text, onEvent, { signal, idempotencyKey } = {}) {
  const document_ids = documentsEnAttente();
  const body = {
    content: text, agent: modeAgent(),
    document_ids: document_ids.length ? document_ids : null,
  };
  try {
    const r = await ouvrirFluxSSE(
      `/intelligence/conversations/${cid}/messages/stream`,
      { body, onEvent, signal, idempotencyKey },
    );
    viderDocumentsEnAttente();
    return r;
  } catch (e) {
    if (e && e.code === "stream_unavailable") return axChatIn(cid, text, { idempotencyKey });
    throw e;
  }
}

/** `axRegenerer`/`axEditerMessage` n'ont pas de route bloquante de repli
 * (contrairement à `axStreamChatIn`) : une indisponibilité réelle du flux est
 * nommée `flux_indisponible` plutôt que laissée fuiter en `stream_unavailable`
 * brut jusqu'à l'utilisateur. */
function nommerFluxIndisponible(e) {
  if (e && e.code === "stream_unavailable") {
    const err = new Error("flux_indisponible");
    err.code = "flux_indisponible";
    throw err;
  }
  throw e;
}

/** Rejoue le dernier tour : supprime la réponse et relance le même flux. */
export async function axRegenerer(cid, msgId, onEvent, { signal, idempotencyKey } = {}) {
  try {
    return await ouvrirFluxSSE(
      `/intelligence/conversations/${cid}/messages/${msgId}/regenerer`,
      { body: {}, onEvent, signal, idempotencyKey },
    );
  } catch (e) { nommerFluxIndisponible(e); }
}

/** Remplace un message envoyé, supprime la suite du fil et relance le flux. */
export async function axEditerMessage(cid, msgId, content, onEvent, { signal, idempotencyKey } = {}) {
  try {
    return await ouvrirFluxSSE(
      `/intelligence/conversations/${cid}/messages/${msgId}/editer`,
      { body: { content }, onEvent, signal, idempotencyKey },
    );
  } catch (e) { nommerFluxIndisponible(e); }
}

// --- intégrations (Notion, Google) ---
export async function axIntegrations() { return axFetch("/integrations/status"); }
/** Ouvre l'autorisation OAuth du fournisseur dans le navigateur. */
export async function axConnectIntegration(provider) {
  const r = await axFetch(`/integrations/${provider}/authorize`, { method: "POST", body: {} });
  if (r.authorize_url) window.location.href = r.authorize_url;
  return r;
}
export async function axDisconnectIntegration(provider) {
  return axFetch(`/integrations/${provider}`, { method: "DELETE" });
}
/** Publie un rapport archivé dans Notion / Drive ; renvoie { url }. */
export async function axDeliverReport(provider, reportId) {
  return axFetch(`/integrations/${provider}/deliver`, {
    method: "POST", body: { report_id: reportId },
  });
}

// --- veille agents (watches) ---
export async function axWatchSkills() { return axFetch("/watches/skills", { auth: false }); }
export async function axListWatches() { return axFetch("/watches"); }
export async function axCreateWatch(body) { return axFetch("/watches", { method: "POST", body }); }
export async function axWatchRuns(id) { return axFetch(`/watches/${id}/runs`); }
export async function axWatchActivity() { return axFetch("/watches/activity"); }
export async function axRunWatch(id) { return axFetch(`/watches/${id}/run`, { method: "POST", body: {} }); }
export async function axPauseWatch(id) { return axFetch(`/watches/${id}/pause`, { method: "POST", body: {} }); }
export async function axResumeWatch(id) { return axFetch(`/watches/${id}/resume`, { method: "POST", body: {} }); }
export async function axDeleteWatch(id) { return axFetch(`/watches/${id}`, { method: "DELETE" }); }
export async function axMetrics(jours = 30) { return axFetch(`/metrics/tableau?jours=${jours}`); }
// Administration des comptes (écran Pilotage, onglet Comptes).
export async function axComptes() { return axFetch("/metrics/comptes"); }
export async function axCrediterCompte(userId, credits, motif) {
  return axFetch(`/metrics/comptes/${userId}/crediter`, { method: "POST", body: { credits, motif } });
}
export async function axProlongerEssai(userId, jours) {
  return axFetch(`/metrics/comptes/${userId}/prolonger`, { method: "POST", body: { jours } });
}
// Visualisation à la volée (chat en flux) : le spec du bloc ```viz → SVG ou tableau de repli.
export async function axRenduViz(spec) { return axFetch("/viz/rendu", { method: "POST", body: spec }); }
export async function axPremierRapport() { return axFetch("/analysis/premier-rapport", { method: "POST" }); }
// Export d'une conversation : on télécharge des octets, pas du JSON — axFetch
// ne convient pas, il parse la réponse.
export async function axExporterConversation(id, format, nomFichier) {
  const r = await fetch(`${AX_API}/intelligence/conversations/${id}/export?format=${format}`, {
    headers: { Authorization: "Bearer " + axGetToken() },
  });
  if (!r.ok) throw new Error("Export impossible");
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomFichier;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Sans révocation, chaque export garde son blob en mémoire jusqu'au
  // rechargement de la page.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function axListFeeds() { return axFetch("/watches/feeds"); }
export async function axFeedsCatalogue() { return axFetch("/watches/feeds/catalogue"); }
export async function axAddFeed(body) { return axFetch("/watches/feeds", { method: "POST", body }); }
export async function axDeleteFeed(id) { return axFetch(`/watches/feeds/${id}`, { method: "DELETE" }); }

// --- documents (user RAG) ---
export async function axListDocuments() { return axFetch("/documents"); }
export async function axDeleteDocument(id) { return axFetch(`/documents/${id}`, { method: "DELETE" }); }
/** Relance l'indexation d'un document déjà importé (`chunk_count = 0`).
 * Renvoie le `DocumentOut` à jour : le front sait tout de suite si la
 * seconde tentative a produit des chunks. */
export async function axReindexerDocument(id) {
  return axFetch(`/documents/${id}/reindexer`, { method: "POST", body: {} });
}
export async function axUploadDocument(file, _retried = false) {
  const tok = axGetToken();
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(AX_API + "/documents/upload", {
    method: "POST",
    headers: tok ? { Authorization: "Bearer " + tok } : {},
    body: fd,
  });
  if ((res.status === 401 || res.status === 403) && !_retried) {
    const ok = await tryRefresh();
    if (ok) return axUploadDocument(file, true);
  }
  if (!res.ok) {
    let msg = "upload failed";
    try { const d = await res.json(); msg = d.detail?.message || d.detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

// --- reports ---

/** Repli bloquant du flux : `POST /analysis/run` crée la ligne, lance le même
 * moteur et ATTEND son terme (arbitrage §0 de la spec). Depuis Task 2 il rend
 * un `ReportDetail` — donc `id`, et non plus `report_id`. On le normalise ici
 * pour que l'appelant n'ait qu'une forme de rapport à connaître, quelle que
 * soit la route qui l'a produit. Non exporté : le seul chemin du front est
 * `axLancerRapport`. */
async function lancerBloquant(body) {
  const r = await axFetch("/analysis/run", { method: "POST", body });
  // `report_id` conservé en alias : le flux le porte sur chaque événement, et
  // l'écran de génération lit la même clé dans les deux cas.
  return r && r.id ? { ...r, report_id: r.id } : r;
}

/** Lance un rapport et suit sa génération (`POST /analysis/stream`).
 *
 * `onEvent` reçoit CHAQUE événement du flux tel quel : le premier porte déjà
 * `report_id`, donc l'écran connaît l'identifiant du rapport avant toute
 * progression et peut le mettre de côté pour reprendre après un rechargement.
 * `signal` permet de lâcher la lecture du flux sans rien annuler côté serveur
 * (le Stop, lui, passe par `axAnnulerRapport` : la tâche tourne dans un autre
 * thread, fermer l'onglet ne l'arrête pas).
 * Renvoie le `ReportDetail` final (+ `balance`), ou le rapport rendu par le
 * repli bloquant si le flux ne s'ouvre pas du tout. */
export async function axLancerRapport(body, onEvent, { signal, idempotencyKey } = {}) {
  try {
    return await ouvrirFluxSSE("/analysis/stream", {
      body, onEvent, signal, idempotencyKey,
      messageInterrompu: "Génération interrompue.",
    });
  } catch (e) {
    if (e && e.code === "stream_unavailable") return lancerBloquant(body);  // repli
    throw e;
  }
}

/** Fenêtre de liste → `{ items, has_more }` (en cours d'abord, puis épinglés,
 * puis par date). `before` = identifiant du dernier rapport déjà affiché. */
export async function axRapports({ limit = 20, before, inclure_archives = false } = {}) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (before) q.set("before", before);
  if (inclure_archives) q.set("inclure_archives", "true");
  return axFetch(`/reports?${q.toString()}`);
}
/** `ReportDetail` : statut, étape, progression, detail, contenu. C'est la
 * source de vérité du suivi — le polling de l'écran de génération l'appelle
 * toutes les 3 s tant que le statut vaut `en_cours`. */
export async function axRapport(id) { return axFetch(`/reports/${id}`); }
/** Stop : pose le drapeau d'annulation. La tâche range le rapport en `annule`
 * entre deux étapes — le statut ne change donc pas dans cette réponse. */
export async function axAnnulerRapport(id) {
  return axFetch(`/reports/${id}/annuler`, { method: "POST", body: {} });
}
/** « Modifier et relancer » / « Recherche élargie » / « Générer quand même » :
 * crée un NOUVEAU rapport, l'ancien est conservé.
 *
 * `idempotencyKey` : même contrat que `axLancerRapport` — une relance est un
 * lancement, donc un débit, et une panne réseau après l'acceptation serveur y
 * exposait au même double débit (revue Task 5, finding 11). L'appelant passe
 * la clé pour pouvoir la REPORTER sur son « Réessayer » ; sans clé, l'en-tête
 * n'est pas envoyée et le serveur se comporte comme avant. */
export async function axRelancerRapport(id, { question, elargir, forcer, idempotencyKey } = {}) {
  return axFetch(`/reports/${id}/relancer`, {
    method: "POST",
    body: { question: question || null, elargir: !!elargir, forcer: !!forcer },
    headers: idempotencyKey ? { "X-Idempotency-Key": idempotencyKey } : undefined,
  });
}
/** « Signaler un problème » / « Votre avis » → `report_feedback` + email
 * technique. Remplace le Google Form. */
export async function axSignalerRapport(id, { motif, note, commentaire } = {}) {
  return axFetch(`/reports/${id}/feedback`, {
    method: "POST",
    body: { motif, note: note || null, commentaire: commentaire || null },
  });
}

/* Images des visualisations — depuis Task 3, `GET /viz/{empreinte}.svg` exige
 * l'authentification (ou `?p=<jeton de partage>` sur la page publique). Un
 * `<img src>` n'envoie aucun en-tête : il ne marche plus. On va donc chercher
 * le SVG nous-mêmes, et l'appelant en fait une URL d'objet.
 *
 * Cache par empreinte : une page de rapport affiche plusieurs graphiques et
 * l'éditeur se remonte à chaque changement de langue ou de thème. Le cache est
 * BORNÉ — sans limite, une session qui parcourt cinquante rapports gardait
 * autant de SVG en mémoire jusqu'au rechargement.
 */
const _CACHE_VIZ = new Map();
const _CACHE_VIZ_MAX = 40;

export async function axVizSvg(empreinte, jetonPartage) {
  const cle = jetonPartage ? `${empreinte}?${jetonPartage}` : empreinte;
  if (_CACHE_VIZ.has(cle)) return _CACHE_VIZ.get(cle);
  const tok = jetonPartage ? null : axGetToken();
  const url = `${AX_API}/viz/${empreinte}.svg`
    + (jetonPartage ? `?p=${encodeURIComponent(jetonPartage)}` : "");
  const res = await fetch(url, {
    headers: tok ? { Authorization: "Bearer " + tok } : {},
  });
  // Un jeton d'accès expiré rend 401 : on le rafraîchit et on rejoue UNE fois,
  // comme `axFetch`. Sans ça, tous les graphiques d'un onglet resté ouvert une
  // heure disparaissaient d'un coup.
  if ((res.status === 401 || res.status === 403) && !jetonPartage) {
    const ok = await tryRefresh();
    if (ok) {
      const rejoue = await fetch(url, {
        headers: { Authorization: "Bearer " + axGetToken() },
      });
      if (!rejoue.ok) throw await erreurDepuisReponse(rejoue, "Graphique indisponible.");
      const svg = await rejoue.text();
      _memoriserViz(cle, svg);
      return svg;
    }
  }
  if (!res.ok) throw await erreurDepuisReponse(res, "Graphique indisponible.");
  const svg = await res.text();
  _memoriserViz(cle, svg);
  return svg;
}

function _memoriserViz(cle, svg) {
  if (_CACHE_VIZ.size >= _CACHE_VIZ_MAX) {
    // Le plus ancien inséré part — `Map` conserve l'ordre d'insertion.
    const premiere = _CACHE_VIZ.keys().next();
    if (!premiere.done) _CACHE_VIZ.delete(premiere.value);
  }
  _CACHE_VIZ.set(cle, svg);
}

/* --- Gestion des rapports (spec §4) -------------------------------------
 *
 * Un seul endpoint côté serveur (`PATCH /reports/{id}`, sémantique PATCH
 * stricte) : quatre fonctions nommées ici plutôt qu'un `axPatchRapport`
 * générique, pour que l'appelant ne compose jamais le corps lui-même — un
 * `{archived: undefined}` parti par erreur ne veut RIEN dire côté serveur,
 * alors qu'un `{archived: null}` veut dire quelque chose.
 */
async function patcherRapport(id, patch) {
  return axFetch(`/reports/${id}`, { method: "PATCH", body: patch });
}
export async function axRenommerRapport(id, titre) {
  return patcherRapport(id, { title: titre });
}
export async function axEpinglerRapport(id, epingle = true) {
  return patcherRapport(id, { pinned: !!epingle });
}
export async function axArchiverRapport(id, archive = true) {
  return patcherRapport(id, { archived: !!archive });
}
/** `projectId === null` retire du dossier (le serveur distingue absent de
 * `null` via `model_fields_set`) : « Retirer du dossier » serait inexprimable
 * autrement. */
export async function axDeplacerRapport(id, projectId) {
  return patcherRapport(id, { project_id: projectId || null });
}
export async function axSupprimerRapport(id) {
  return axFetch(`/reports/${id}`, { method: "DELETE" });
}
/** Recherche titre + contenu, avec extrait. Le serveur refuse (400
 * `requete_trop_courte`) sous 3 caractères : c'est l'appelant qui garde le
 * seuil, aucun aller-retour pour deux lettres. */
export async function axRechercherRapports(q) {
  return axFetch(`/reports/search?q=${encodeURIComponent(q)}`);
}

/* --- Partage public (spec §0) -------------------------------------------- */

/** Crée (ou retrouve — la route est idempotente) le lien public.
 * Rend `{ jeton, url }`, `url` étant un chemin RELATIF : l'adresse publique du
 * front n'est pas une donnée du backend, c'est la vue qui préfixe avec
 * `window.location.origin`. */
export async function axPartagerRapport(id) {
  return axFetch(`/reports/${id}/partage`, { method: "POST", body: {} });
}
/** Révoque le lien. Idempotent ; un nouveau partage rendra un jeton NEUF,
 * l'ancien lien reste mort. */
export async function axRevoquerPartage(id) {
  return axFetch(`/reports/${id}/partage`, { method: "DELETE" });
}

/* --- Export (spec §4) ---------------------------------------------------- */

/** `GET /reports/{id}/export?format=pdf|md|docx` → téléchargement.
 *
 * Remplace `axDownloadReportPdf` : les trois formats partent du même markdown
 * archivé côté serveur, il n'y a aucune raison d'avoir un chemin front par
 * format. `axFetch` ne convient pas — on télécharge des octets, pas du JSON.
 */
const EXTENSIONS_EXPORT = { pdf: "pdf", md: "md", docx: "docx" };

export async function axExporterRapport(reportId, format, nomFichier, _retried = false) {
  const fmt = EXTENSIONS_EXPORT[format] ? format : "pdf";
  const tok = axGetToken();
  const res = await fetch(`${AX_API}/reports/${reportId}/export?format=${fmt}`, {
    headers: tok ? { Authorization: "Bearer " + tok } : {},
  });
  // Un 401 sur un onglet resté ouvert une heure : même rejeu UNIQUE que
  // `axFetch` (le drapeau compte — un serveur qui rend 401 malgré un
  // rafraîchissement réussi ferait boucler la fonction sur elle-même).
  if ((res.status === 401 || res.status === 403) && !_retried && (await tryRefresh())) {
    return axExporterRapport(reportId, fmt, nomFichier, true);
  }
  if (!res.ok) throw await erreurDepuisReponse(res, "Export impossible.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomFichier || `rapport-axial.${EXTENSIONS_EXPORT[fmt]}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Sans révocation, chaque export garde son blob en mémoire jusqu'au
  // rechargement de la page.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
