/**
 * Small fetch wrapper. All routes live under /api (Vite proxies to :8000 in dev,
 * FastAPI serves both in production).
 */
import i18next from "i18next";

export interface ApiError {
  /** HTTP status. 0 means the backend could not be reached. */
  status: number;
  code: string;
  message: string;
}

export const BACKEND_UNREACHABLE = "backend_unreachable";

export function isApiError(e: unknown): e is ApiError {
  return typeof e === "object" && e !== null && "status" in e && "code" in e && "message" in e;
}

export function isUnreachable(e: unknown): boolean {
  return isApiError(e) && e.status === 0;
}

const TOKEN_KEY = "halqa.token";
const USER_KEY = "halqa.user";

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function storeSession(token: string, user: unknown) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* storage blocked: the session lasts until reload */
  }
}

export function readStoredUser<T>(): T | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function clearSession() {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}

type Listener = () => void;
const unauthorizedListeners = new Set<Listener>();
/** The auth provider subscribes here so a 401 anywhere signs the user out. */
export function onUnauthorized(fn: Listener): () => void {
  unauthorizedListeners.add(fn);
  return () => {
    unauthorizedListeners.delete(fn);
  };
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  signal?: AbortSignal;
  /** Skip the bearer token (public routes). */
  anonymous?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = path.startsWith("/api") ? path : `/api${path.startsWith("/") ? "" : "/"}${path}`;
  if (!query) return url;
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const qs = sp.toString();
  return qs ? `${url}?${qs}` : url;
}

function normalise(status: number, payload: unknown, fallback: string): ApiError {
  // FastAPI shapes: {detail: "text"} | {detail: {code, message}} | {code, message} | {detail: [{msg}]}
  let code = `http_${status}`;
  let message = fallback;
  if (payload && typeof payload === "object") {
    const p = payload as Record<string, unknown>;
    const d = p.detail ?? p;
    if (typeof d === "string") {
      message = d;
    } else if (Array.isArray(d)) {
      message = d
        .map((x) => (x && typeof x === "object" && "msg" in x ? String((x as { msg: unknown }).msg) : String(x)))
        .join("; ");
      code = "validation_error";
    } else if (d && typeof d === "object") {
      const o = d as Record<string, unknown>;
      if (typeof o.code === "string") code = o.code;
      if (typeof o.message === "string") message = o.message;
    }
  }
  return { status, code, message };
}

export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Accept-Language": (i18next.language || "en").slice(0, 2),
  };
  const token = opts.anonymous ? null : getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: string | undefined;
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), {
      method: opts.method ?? (body ? "POST" : "GET"),
      headers,
      body,
      signal: opts.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    const err: ApiError = { status: 0, code: "network_error", message: BACKEND_UNREACHABLE };
    throw err;
  }

  const text = await res.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!res.ok) {
    // The dev proxy answers 500/502/503/504 with an empty or HTML body when the backend is down.
    const unreachable =
      res.status === 502 || res.status === 503 || res.status === 504 || (res.status === 500 && payload === null);
    const err: ApiError = unreachable
      ? { status: 0, code: "network_error", message: BACKEND_UNREACHABLE }
      : normalise(res.status, payload, res.statusText || "Request failed");
    if (res.status === 401 && !opts.anonymous) {
      clearSession();
      unauthorizedListeners.forEach((fn) => fn());
    }
    throw err;
  }
  return payload as T;
}
