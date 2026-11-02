import { useCallback, useEffect, useState } from "react";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (res.status === 428 && !location.pathname.startsWith("/setup")) {
    location.assign("/setup");
    throw new ApiError("setup required", 428);
  }
  const text = await res.text();
  let body: any = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiError(`Bad JSON (${res.status})`, res.status);
  }
  if (!res.ok) throw new ApiError(body?.error ?? `Failed (${res.status})`, res.status);
  return (body?.data ?? body) as T;
}

export const api = {
  get: <T,>(p: string) => request<T>(p),
  post: <T,>(p: string, d?: unknown) => request<T>(p, { method: "POST", body: JSON.stringify(d ?? {}) }),
  put: <T,>(p: string, d?: unknown) => request<T>(p, { method: "PUT", body: JSON.stringify(d ?? {}) }),
  patch: <T,>(p: string, d?: unknown) => request<T>(p, { method: "PATCH", body: JSON.stringify(d ?? {}) }),
  del: <T,>(p: string) => request<T>(p, { method: "DELETE" }),
};

export interface UseApiOptions {
  /** Poll interval in milliseconds. Omit for a one-shot fetch. */
  interval?: number;
  /** When false the request is skipped (and any poll is stopped). */
  enabled?: boolean;
  /** Extra values that should trigger a refetch when they change. */
  deps?: unknown[];
}

export interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  /** Refetch now. */
  refresh: () => void;
}

/**
 * Fetch an API path (relative to `/api`) with optional polling.
 *
 * Passing `null` as the path clears the state, which is how pages handle
 * "no device selected": `useApi(serial ? `/devices/${serial}` : null)`.
 */
export function useApi<T>(
  path: string | null,
  { interval, enabled = true, deps = [] }: UseApiOptions = {},
): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(path) && enabled);
  const [error, setError] = useState<Error | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!path || !enabled) {
      if (!path) {
        setData(null);
        setError(null);
      }
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    const load = async () => {
      try {
        const result = await request<T>(path);
        if (cancelled) return;
        setData(result);
        setError(null);
      } catch (exc) {
        if (cancelled) return;
        setError(exc instanceof Error ? exc : new Error(String(exc)));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();

    if (interval && interval > 0) {
      const timer = window.setInterval(() => void load(), interval);
      return () => {
        cancelled = true;
        window.clearInterval(timer);
      };
    }
    return () => {
      cancelled = true;
    };
    // `deps` is spread so callers control the dependency list explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, enabled, interval, nonce, ...deps]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return { data, loading, error, refresh };
}
