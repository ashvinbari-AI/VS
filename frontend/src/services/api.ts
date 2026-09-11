import type { ApiResponse } from "../types/api";

/** Thin fetch wrapper that unwraps the {success,data,error} envelope every
 * backend route returns (spec section 36) and throws a readable Error on
 * failure so callers/useApi can render a consistent error state. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  let body: ApiResponse<T>;
  try {
    body = await res.json();
  } catch {
    throw new Error(`Backend returned a non-JSON response (HTTP ${res.status}). Is it running?`);
  }
  if (!body.success) {
    throw new Error(body.error?.message ?? `Request failed (HTTP ${res.status})`);
  }
  return body.data as T;
}

function qs(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      value.forEach((v) => search.append(key, String(v)));
    } else {
      search.set(key, String(value));
    }
  }
  const str = search.toString();
  return str ? `?${str}` : "";
}

export const api = {
  get: <T>(path: string, params: Record<string, unknown> = {}) =>
    request<T>(`${path}${qs(params)}`),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
