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

function toErrorMessage(detail: unknown, status: number): string {
  if (!detail) {
    return `Request failed with status ${status}`;
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (typeof detail === "object") {
    const record = detail as { detail?: unknown; message?: unknown };
    if (typeof record.detail === "string") {
      return record.detail;
    }
    if (Array.isArray(record.detail) && record.detail.length > 0) {
      const first = record.detail[0] as { msg?: unknown };
      if (typeof first?.msg === "string") {
        return first.msg;
      }
    }
    if (typeof record.message === "string") {
      return record.message;
    }
  }
  return `Request failed with status ${status}`;
}

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

function shouldSuppressApiErrorLog(path: string, status: number): boolean {
  // Legacy candidates can exist without candidate-management timeline rows.
  if (
    status === 404 &&
    /^\/candidate-management\/candidates\/[^/]+\/interactions(?:\?|$)/.test(path)
  ) {
    return true;
  }
  // Candidate is already submitted to this job (idempotent UX flow).
  if (status === 409 && /^\/jobs\/[^/]+\/submit(?:\?|$)/.test(path)) {
    return true;
  }
  return false;
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
    const expectedCandidateConflict =
      response.status === 409 &&
      (path.includes("/candidate-management/candidates") || /^\/jobs\/[^/]+\/submit(?:\?|$)/.test(path));

    if (expectedCandidateConflict) {
      // Expected domain conflict; avoid noisy dev overlay.
      console.warn(`[API Conflict] ${response.status} ${path}: candidate already exists or conflicting payload`);
    } else {
      console.error(`[API Error] ${response.status} ${path}:`, detail);
    }
    throw new ApiError(message, response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
