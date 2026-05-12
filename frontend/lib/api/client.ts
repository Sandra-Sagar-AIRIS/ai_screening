export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

// ---------------------------------------------------------------------------
// Lightweight GET-request cache (prevents duplicate in-flight + re-render fetches)
// ---------------------------------------------------------------------------
type CacheEntry = { data: unknown; expiresAt: number; inflight?: Promise<unknown> };
const _getCache = new Map<string, CacheEntry>();
const _GET_CACHE_TTL_MS = 30_000; // 30 s — safe for list endpoints that poll anyway

/** Expose for manual invalidation (e.g. after mutations). */
export function invalidateApiCache(pathPrefix?: string) {
  if (!pathPrefix) {
    _getCache.clear();
    return;
  }
  for (const key of _getCache.keys()) {
    if (key.startsWith(pathPrefix)) _getCache.delete(key);
  }
}

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
  /** Abort the request after this many milliseconds (non-blocking server work should not require long waits). */
  timeoutMs?: number;
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
  // Mixed candidate stores: ATS route may 404 for candidate-management-only IDs.
  if (status === 404 && /^\/candidates\/[^/]+\/matches(?:\?|$)/.test(path)) {
    return true;
  }
  // Older backends without POST /jobs/{id}/submit, or rollout mismatch — candidates page PATCH-fallback.
  if (status === 404 && /^\/jobs\/[^/]+\/submit(?:\?|$)/.test(path)) {
    return true;
  }
  // Rescore 404 is expected when the candidate has no job submissions / ATS rows yet.
  if (status === 404 && /^\/candidates\/[^/]+\/rescore(?:\?|$)/.test(path)) {
    return true;
  }
  // Candidate is already submitted to this job (idempotent UX flow).
  if (status === 409 && /^\/jobs\/[^/]+\/submit(?:\?|$)/.test(path)) {
    return true;
  }
  // Duplicate feedback or claim submission — expected domain conflict, not a bug.
  if (status === 409 && /^\/interviews\/[^/]+\/(feedback|claim)(?:\?|$)/.test(path)) {
    return true;
  }
  // Some pages optionally fetch org users for dropdowns; 403/500 are non-blocking there.
  if ((status === 403 || status === 500) && /^\/users(?:\?|$|\/)/.test(path)) {
    return true;
  }
  // Interviews feature may not be set up for all candidates/orgs.
  if (status === 500 && /^\/candidate-management\/candidates\/[^/]+\/interviews(?:\?|$)/.test(path)) {
    return true;
  }
  return false;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
  /** Override the default 30 s GET-cache TTL. Pass 0 to skip caching entirely. */
  cacheTtlMs: number = _GET_CACHE_TTL_MS,
): Promise<T> {
  const { auth = true, timeoutMs, headers, signal: userSignal, ...rest } = options;
  const method = (rest.method ?? "GET").toUpperCase();

  // Only cache GET requests executed in a browser context.
  if (method === "GET" && cacheTtlMs > 0 && typeof window !== "undefined") {
    const now = Date.now();
    const hit = _getCache.get(path);
    if (hit) {
      // Return live or in-flight data without an extra network round-trip.
      if (hit.expiresAt > now) return hit.data as T;
      if (hit.inflight) return hit.inflight as Promise<T>;
    }
    // Prime the inflight dedup slot before the fetch starts.
    const entry: CacheEntry = { data: undefined, expiresAt: 0 };
    _getCache.set(path, entry);
    entry.inflight = _fetchRaw<T>(path, options).then((result) => {
      entry.data = result;
      entry.expiresAt = Date.now() + cacheTtlMs;
      entry.inflight = undefined;
      return result;
    }).catch((err) => {
      _getCache.delete(path);
      throw err;
    });
    return entry.inflight as Promise<T>;
  }

  // Non-GET or cache disabled — go straight to the network.
  return _fetchRaw<T>(path, options);
}

async function _fetchRaw<T>(path: string, options: RequestOptions): Promise<T> {
  const { auth = true, timeoutMs, headers, signal: userSignal, ...rest } = options;
  const token = auth ? getAuthToken() : null;

  const abortController = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  if (timeoutMs != null && timeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => abortController.abort(), timeoutMs);
  }
  if (userSignal) {
    if (userSignal.aborted) {
      abortController.abort();
    } else {
      userSignal.addEventListener("abort", () => abortController.abort(), { once: true });
    }
  }
  const signal = abortController.signal;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    });
  } catch (error: unknown) {
    const aborted =
      error instanceof Error && error.name === "AbortError";
    if (aborted) {
      const message =
        timeoutMs != null && timeoutMs > 0
          ? `Request timed out after ${timeoutMs / 1000}s. The server may still be processing — try refreshing.`
          : "Request was cancelled.";
      throw new ApiError(message, 0, error);
    }
    const message =
      "Cannot reach the API server. Verify backend is running and CORS/API base URL are correct.";
    console.error(`[API Network Error] ${path}:`, error);
    throw new ApiError(message, 0, error);
  } finally {
    if (timeoutId !== undefined) {
      globalThis.clearTimeout(timeoutId);
    }
  }

  if (!response.ok) {
    if (response.status === 401 && typeof window !== "undefined") {
      try {
        window.localStorage.removeItem("airis_access_token");
      } catch {
        /* ignore */
      }
      window.location.replace("/login");
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
    const suppressErrorLog = shouldSuppressApiErrorLog(path, response.status);

    if (expectedCandidateConflict) {
      // Expected domain conflict; avoid noisy dev overlay.
      console.warn(`[API Conflict] ${response.status} ${path}: candidate already exists or conflicting payload`);
    } else if (suppressErrorLog) {
      console.warn(`[API Expected] ${response.status} ${path}: suppressed noisy error log`);
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
