"use client";
// API bridge between the prototype UI and the Axial backend.
// Keeps the exact prototype code intact; screens call these helpers instead of
// their mock stubs, one seam at a time.

export const AX_API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8090";
const TOKEN_KEY = "axial_token";

export function axSetToken(t) {
  try { localStorage.setItem(TOKEN_KEY, t); } catch (e) {}
}
export function axGetToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
}
export function axClearToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch (e) {}
}

export async function axFetch(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  const tok = auth ? axGetToken() : null;
  if (tok) headers["Authorization"] = "Bearer " + tok;
  const res = await fetch(AX_API + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
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
  axSetToken(r.access_token);
  return r.user;
}
export async function axLogin(email, password) {
  const r = await axFetch("/auth/login", {
    method: "POST", auth: false, body: { email, password },
  });
  axSetToken(r.access_token);
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

/** Send a chat message; returns the assistant reply { content, agent, citations }. */
export async function axChat(text) {
  const cid = await ensureConversation();
  return axFetch(`/intelligence/conversations/${cid}/messages`, {
    method: "POST", body: { content: text },
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
export async function axUploadDocument(file) {
  const tok = axGetToken();
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(AX_API + "/documents/upload", {
    method: "POST",
    headers: tok ? { Authorization: "Bearer " + tok } : {},
    body: fd,
  });
  if (!res.ok) {
    let msg = "upload failed";
    try { const d = await res.json(); msg = d.detail?.message || d.detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}

// --- reports ---
export async function axRunAnalysis(body) { return axFetch("/analysis/run", { method: "POST", body }); }
export async function axCreateReport(body) { return axFetch("/reports", { method: "POST", body }); }
export async function axListReports() { return axFetch("/reports"); }

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
