// API client. Session is carried by the HttpOnly cookie (credentials: include).
// The backend returns a stable error envelope {code,...}; we surface `code` so the UI
// can translate it (§4.6.2) — we never display backend natural-language text directly.

export interface ApiError {
  code: string;
  details?: Record<string, unknown>;
  request_id?: string;
}

export class ApiException extends Error {
  constructor(public readonly error: ApiError, public readonly status: number) {
    super(error.code);
  }
}

const apiBase = (): string =>
  (window as unknown as { __APP_CONFIG__?: { apiBase: string } }).__APP_CONFIG__?.apiBase ?? "/admin-api/v1";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiBase() + path, {
      method,
      credentials: "include",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiException({ code: "NETWORK_ERROR" }, 0);
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({ code: "SYSTEM_INTERNAL_ERROR" }));
  if (!res.ok) throw new ApiException(data as ApiError, res.status);
  return data as T;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, b?: unknown) => request<T>("POST", p, b),
  patch: <T>(p: string, b?: unknown) => request<T>("PATCH", p, b),
  del: <T>(p: string) => request<T>("DELETE", p),
};
