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
  del: <T,>(p: string) => request<T>(p, { method: "DELETE" }),
};
