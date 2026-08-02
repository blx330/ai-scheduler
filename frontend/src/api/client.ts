import type { ApiErrorBody } from "./types";

export class ApiError extends Error {
  status: number;
  detail: ApiErrorBody["detail"] | undefined;

  constructor(status: number, message: string, detail?: ApiErrorBody["detail"]) {
    super(message);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}

const BASE_URL = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let message = response.statusText;
    let detail: ApiErrorBody["detail"] | undefined;
    try {
      const body = (await response.json()) as ApiErrorBody;
      if (body?.detail) {
        detail = body.detail;
        message = typeof body.detail === "string" ? body.detail : body.detail.message;
      }
    } catch {
      // response had no JSON body
    }
    throw new ApiError(response.status, message, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
