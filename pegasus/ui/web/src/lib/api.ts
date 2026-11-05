/** HTTP client for the Pegasus web GUI.
 *
 *  Two call styles coexist in the pages: bare paths ("/devices") and
 *  explicitly prefixed paths ("/api/catalog"). Both normalise onto a single
 *  base here so no page has to change.
 */
import { useCallback, useEffect, useRef, useState } from "react";

const RAW_BASE = String(import.meta.env?.VITE_API_BASE ?? "").replace(/\/+$/, "");
const BASE_IS_PREFIXED = /\/api$/i.test(RAW_BASE);
const API_ROOT = BASE_IS_PREFIXED ? RAW_BASE.replace(/\/api$/i, "") : RAW_BASE;

const DEFAULT_TIMEOUT = 30_000;

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** Resolve a caller path onto the API root, exactly once. */
export function resolveUrl(path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  const alreadyPrefixed = clean === "/api" || clean.startsWith("/api/");
  if (alreadyPrefixed) return `${API_ROOT}${clean}`;
  return `${API_ROOT}/api${clean}`;
}

function csrf(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)(?:csrf_token|csrf)=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

interface RequestOptions {
  timeout?: number;
  signal?: AbortSignal;
  keepalive?: boolean;
}

async function request<T>(method: string, path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeout ?? DEFAULT_TIMEOUT);
  const onAbort = () => controller.abort();
  options.signal?.addEventListener("abort", onAbort);

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = csrf();
  if (token) headers["X-CSRF-Token"] = token;

  try {
    const response = await fetch(resolveUrl(path), {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      keepalive: options.keepalive,
    });

    if (response.status === 204) return undefined as T;

    const text = await response.text();
    let parsed: unknown = null;
    if (text) {
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = text;
      }
    }

    const envelope = parsed as { ok?: boolean; data?: unknown; error?: unknown } | null;
    const failed = envelope && typeof envelope === "object" && envelope.ok === false;

    if (!response.ok || failed) {
      const message =
        (envelope && typeof envelope.error === "string" && envelope.error) ||
        (typeof parsed === "string" && parsed) ||
        `${response.status} ${response.statusText}`.trim();
      if (response.status === 428 && !window.location.pathname.startsWith("/setup")) {
        window.location.assign("/setup");
      }
      throw new ApiError(message, response.status, parsed);
    }

    if (envelope && typeof envelope === "object" && "ok" in envelope) {
      return (envelope.data ?? null) as T;
    }
    return parsed as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if ((error as Error)?.name === "AbortError") {
      throw new ApiError("request timed out", 0, null);
    }
    throw new ApiError((error as Error)?.message || "network error", 0, null);
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", onAbort);
  }
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>("GET", path, undefined, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>("POST", path, body, options),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>("PUT", path, body, options),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>("PATCH", path, body, options),
  del: <T>(path: string, options?: RequestOptions) => request<T>("DELETE", path, undefined, options),
};

export interface UseApiOptions {
  interval?: number;
  enabled?: boolean;
  deps?: unknown[];
}

export interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => void;
}

/** Poll a path. A null path suspends the request without unmounting. */
export function useApi<T>(path: string | null, options: UseApiOptions = {}): UseApiResult<T> {
  const { interval, enabled = true, deps = [] } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const serial = useRef(0);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);

  const fetchNow = useCallback(async () => {
    if (!path || !enabled) return;
    const ticket = ++serial.current;
    setLoading(true);
    try {
      const result = await api.get<T>(path);
      if (!active.current || ticket !== serial.current) return;
      setData(result);
      setError(null);
    } catch (caught) {
      if (!active.current || ticket !== serial.current) return;
      setError(caught as Error);
    } finally {
      if (active.current && ticket === serial.current) setLoading(false);
    }
  }, [path, enabled]);

  const refresh = useCallback(() => {
    void fetchNow();
  }, [fetchNow]);

  useEffect(() => {
    void fetchNow();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchNow, ...deps]);

  useEffect(() => {
    if (!interval || !path || !enabled) return;
    const timer = setInterval(() => void fetchNow(), interval);
    return () => clearInterval(timer);
  }, [interval, path, enabled, fetchNow]);

  return { data, loading, error, refresh };
}

export default api;
