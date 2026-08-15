// Typed API client for the Axial backend.
// Base URL is the FastAPI app (default: http://localhost:8080).

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
};

export async function apiFetch<T>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (opts.token) headers["Authorization"] = `Bearer ${opts.token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });

  if (!res.ok) {
    let detail = res.statusText;
    let code: string | undefined;
    try {
      const data = await res.json();
      detail = data.detail?.message ?? data.detail ?? data.message ?? detail;
      code = data.detail?.code ?? data.code;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(detail, res.status, code);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// Convenience wrappers.
export const api = {
  get: <T>(p: string, token?: string | null) => apiFetch<T>(p, { token }),
  post: <T>(p: string, body?: unknown, token?: string | null) =>
    apiFetch<T>(p, { method: "POST", body, token }),
  put: <T>(p: string, body?: unknown, token?: string | null) =>
    apiFetch<T>(p, { method: "PUT", body, token }),
  del: <T>(p: string, token?: string | null) =>
    apiFetch<T>(p, { method: "DELETE", token }),
};
