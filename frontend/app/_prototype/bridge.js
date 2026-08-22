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
      if (!res.ok) { axClearToken(); return false; }
      const d = await res.json();
      axSetToken(d.access_token, d.refresh_token);
      return true;
    } catch (e) { return false; }
    finally { setTimeout(() => { _refreshing = null; }, 0); }
  })();
  return _refreshing;
}

export async function axFetch(path, { method = "GET", body, auth = true, _retried = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  const tok = auth ? axGetToken() : null;
  if (tok) headers["Authorization"] = "Bearer " + tok;
  const res = await fetch(AX_API + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && auth && !_retried && path !== "/auth/refresh") {
    const ok = await tryRefresh();
    if (ok) return axFetch(path, { method, body, auth, _retried: true });
  }
  if (!res.ok) {
    let msg = res.statusText, code;
    try {
      const d = await res.json();
      msg = d.detail?.message || d.detail || d.message || msg;
      code = d.detail?.code || d.code;
    } catch (e) {}
    const err = new Error(msg);
    err.status = res.status;
    err.code = code;
    throw err;
  }
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

// --- chat / analysis (Workspace) ---
let _convId = null;

async function ensureConversation(forceNew = false) {
  if (_convId && !forceNew) return _convId;
  let projects = await axFetch("/intelligence/projects");
  if (!projects.length) {
    projects = [await axFetch("/intelligence/projects", { method: "POST", body: { name: "Workspace" } })];
  }
  const pid = projects[0].id;
  if (forceNew) {
    const created = await axFetch(`/intelligence/projects/${pid}/conversations`, {
      method: "POST", body: { title: "Workspace" },
    });
    _convId = created.id;
    return _convId;
  }
  const convs = await axFetch(`/intelligence/projects/${pid}/conversations`);
  const conv = convs.length
    ? convs[0]
    : await axFetch(`/intelligence/projects/${pid}/conversations`, {
        method: "POST", body: { title: "Workspace" },
      });
  _convId = conv.id;
  return _convId;
}

/** Force the next axChat to target a brand-new backend conversation. */
export async function axNewConversation() {
  return ensureConversation(true);
}

/** Send a chat message; returns the assistant reply { content, agent, citations }.
 * The workspace mode selector persists the chosen agent in localStorage:
 * "auto" (conversation libre, routing par intention) or an explicit persona key. */
export async function axChat(text) {
  const cid = await ensureConversation();
  return axChatIn(cid, text);
}
/** Send a chat message into a SPECIFIC backend conversation.
 * Attaches any documents queued via the composer (window.AXIAL_PENDING_DOCS):
 * they are injected directly into THIS message's context, like an attachment. */
export async function axChatIn(cid, text) {
  let agent = "auto";
  try { agent = localStorage.getItem("axial_agent_mode") || "auto"; } catch (e) {}
  const pending = (typeof window !== "undefined" && window.AXIAL_PENDING_DOCS) || [];
  const document_ids = pending.map((d) => d.id);
  const r = await axFetch(`/intelligence/conversations/${cid}/messages`, {
    method: "POST", body: { content: text, agent, document_ids: document_ids.length ? document_ids : null },
  });
  if (typeof window !== "undefined") window.AXIAL_PENDING_DOCS = [];
  try { window.dispatchEvent(new Event("axial-pending-docs")); } catch (e) {}
  return r;
}
/** Streamed chat answer: onEvent({step, delta, citations}) fires as words arrive.
 * Returns the final persisted message. Falls back to the blocking route if the
 * stream can't be opened. */
export async function axStreamChatIn(cid, text, onEvent) {
  let agent = "auto";
  try { agent = localStorage.getItem("axial_agent_mode") || "auto"; } catch (e) {}
  const pending = (typeof window !== "undefined" && window.AXIAL_PENDING_DOCS) || [];
  const document_ids = pending.map((d) => d.id);
  const body = { content: text, agent, document_ids: document_ids.length ? document_ids : null };

  const run = async (retried) => {
    const tok = axGetToken();
    const res = await fetch(AX_API + `/intelligence/conversations/${cid}/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(tok ? { Authorization: "Bearer " + tok } : {}) },
      body: JSON.stringify(body),
    });
    if (res.status === 401 && !retried) {
      const ok = await tryRefresh();
      if (ok) return run(true);
    }
    if (!res.ok || !res.body) { const e = new Error("stream_unavailable"); e.status = res.status; throw e; }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "", final = null;
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
    if (!final) throw new Error("Réponse interrompue.");
    return final;
  };

  try {
    const r = await run(false);
    if (typeof window !== "undefined") window.AXIAL_PENDING_DOCS = [];
    try { window.dispatchEvent(new Event("axial-pending-docs")); } catch (e) {}
    return r;
  } catch (e) {
    if (e && e.message === "stream_unavailable") return axChatIn(cid, text);  // repli
    throw e;
  }
}

/** Create a fresh backend conversation and return its id. */
export async function axCreateConversation() {
  return ensureConversation(true);
}
/** List the user's conversations (first project). */
export async function axListConversations() {
  const projects = await axFetch("/intelligence/projects");
  if (!projects.length) return [];
  return axFetch(`/intelligence/projects/${projects[0].id}/conversations`);
}
/** Full message history of one conversation. */
export async function axMessages(cid) {
  return axFetch(`/intelligence/conversations/${cid}/messages`);
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
export async function axListFeeds() { return axFetch("/watches/feeds"); }
export async function axAddFeed(body) { return axFetch("/watches/feeds", { method: "POST", body }); }
export async function axDeleteFeed(id) { return axFetch(`/watches/feeds/${id}`, { method: "DELETE" }); }

// --- documents (user RAG) ---
export async function axListDocuments() { return axFetch("/documents"); }
export async function axDeleteDocument(id) { return axFetch(`/documents/${id}`, { method: "DELETE" }); }
export async function axUploadDocument(file, _retried = false) {
  const tok = axGetToken();
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(AX_API + "/documents/upload", {
    method: "POST",
    headers: tok ? { Authorization: "Bearer " + tok } : {},
    body: fd,
  });
  if (res.status === 401 && !_retried) {
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
export async function axRunAnalysis(body) { return axFetch("/analysis/run", { method: "POST", body }); }
/** Streamed analysis: real progress events, then the finished report.
 * onEvent({progress, step, message}) fires as the backend advances.
 * Returns the final report payload. Falls back to the blocking route on 401
 * retry or when streaming isn't available. */
export async function axStreamAnalysis(body, onEvent) {
  const run = async (retried) => {
    const tok = axGetToken();
    const res = await fetch(AX_API + "/analysis/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(tok ? { Authorization: "Bearer " + tok } : {}) },
      body: JSON.stringify(body),
    });
    if (res.status === 401 && !retried) {
      const ok = await tryRefresh();
      if (ok) return run(true);
    }
    if (!res.ok || !res.body) {
      const err = new Error("stream_unavailable");
      err.status = res.status;
      throw err;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "", final = null;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // SSE frames are separated by a blank line.
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
    if (!final) throw new Error("Génération interrompue.");
    return final;
  };
  try {
    return await run(false);
  } catch (e) {
    if (e && e.message === "stream_unavailable") return axRunAnalysis(body);  // repli
    throw e;
  }
}
export async function axCreateReport(body) { return axFetch("/reports", { method: "POST", body }); }
export async function axListReports() { return axFetch("/reports"); }
export async function axGetReport(id) { return axFetch(`/reports/${id}`); }

/** Fetch a report's PDF with auth and trigger a browser download. */
export async function axDownloadReportPdf(reportId, filename) {
  const tok = axGetToken();
  const res = await fetch(`${AX_API}/reports/${reportId}/pdf`, {
    headers: tok ? { Authorization: "Bearer " + tok } : {},
  });
  if (!res.ok) throw new Error("PDF export failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "rapport-axial.pdf";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
