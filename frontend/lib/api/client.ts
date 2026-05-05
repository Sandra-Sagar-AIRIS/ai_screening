export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

<<<<<<< HEAD
function toErrorMessage(detail: unknown, status: number): string {
  if (!detail) {
    return `Request failed with status ${status}`;
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (typeof detail === "object") {
    if ("detail" in detail) {
      const raw = (detail as { detail: unknown }).detail;
      if (typeof raw === "string") {
        return raw;
      }
      if (raw && typeof raw === "object") {
        if ("error" in raw) {
          return String((raw as { error: unknown }).error);
        }
        try {
          return JSON.stringify(raw);
        } catch {
          return "Request failed";
        }
      }
      return String(raw);
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return `Request failed with status ${status}`;
    }
  }
  return `Request failed with status ${status}`;
=======
/** Maps HTTP status to short, user-facing copy (403/401-aware). */
export function formatApiErrorForUser(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 403) {
      return "You don't have permission to perform this action.";
    }
    if (err.status === 401) {
      return "Your session expired. Please sign in again.";
    }
    return err.message;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return "Something went wrong. Please try again.";
>>>>>>> 3b3e2c07 (new roles and recruiter dashboard)
}

type RequestOptions = RequestInit & {
  auth?: boolean;
};

function getAuthToken() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem("airis_access_token");
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { auth = true, headers, ...rest } = options;
  const token = auth ? getAuthToken() : null;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      try {
        window.localStorage.removeItem("airis_access_token");
      } catch {
        /* ignore */
      }
      window.location.assign("/login");
    }
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const message = toErrorMessage(detail, response.status);
    console.error(`[API Error] ${response.status} ${path}:`, detail);
    throw new ApiError(message, response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
