"use client";

import { useCallback, useEffect, useState } from "react";
import { Search, Loader2, Sparkles } from "lucide-react";

import { useAuthStore } from "@/store/auth-store";
import {
  startSourcingSession,
  listSourcingSessions,
  listSourcingResults,
  type SourcingSession,
  type SourcingResult,
  type SessionStatusResponse,
  type ResultAction,
} from "@/lib/api/sourcing";
import { CandidateCard } from "@/components/sourcing/CandidateCard";
import { useSessionPoller } from "@/components/sourcing/useSessionPoller";

// ── Filters ───────────────────────────────────────────────────────────────────

const ACTION_FILTERS: { label: string; value: ResultAction | "" }[] = [
  { label: "All", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Shortlisted", value: "shortlisted" },
  { label: "Rejected", value: "rejected" },
  { label: "Imported", value: "imported" },
];

const TIER_FILTERS = ["", "Strong", "Good", "Moderate", "Weak"];

// ── Start Session Dialog ──────────────────────────────────────────────────────

function StartSessionDialog({
  open,
  onClose,
  onStarted,
}: {
  open: boolean;
  onClose: () => void;
  onStarted: (sessionId: string) => void;
}) {
  const [jdText, setJdText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!jdText.trim() || jdText.trim().length < 20) {
      setError("Please enter at least 20 characters of job description.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { session_id } = await startSourcingSession({ jd_text: jdText });
      onStarted(session_id);
      setJdText("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start session.");
    } finally {
      setLoading(false);
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !loading) onClose();
      }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 p-6 space-y-4">
        <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-[#FF5A1F]" />
          Start AI Sourcing Session
        </h2>
        <p className="text-sm text-gray-500">
          Paste a job description and AIRIS will search internal and external sources for matching candidates.
        </p>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-3">
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            rows={8}
            placeholder="Paste the full job description here…"
            className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#FF5A1F]/30 resize-y"
            disabled={loading}
          />
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm rounded-xl border border-gray-200 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 text-sm font-medium rounded-xl bg-[#FF5A1F] text-white hover:bg-[#e04f1a] disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {loading ? "Starting…" : "Start Sourcing"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SourcePage() {
  const role = useAuthStore((state) => state.role);

  const [sessions, setSessions] = useState<SourcingSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatusResponse | null>(null);
  const [results, setResults] = useState<SourcingResult[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [page, setPage] = useState(1);

  const [actionFilter, setActionFilter] = useState<ResultAction | "">("");
  const [tierFilter, setTierFilter] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingResults, setLoadingResults] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Load sessions ─────────────────────────────────────────────────────────

  useEffect(() => {
    if (role !== "admin" && role !== "recruiter") {
      setLoadingSessions(false);
      return;
    }
    void (async () => {
      try {
        const list = await listSourcingSessions({ page: 1, page_size: 20 });
        setSessions(list);
        if (list.length > 0 && !activeSessionId) {
          setActiveSessionId(list[0].id);
        }
      } catch {
        setError("Failed to load sessions.");
      } finally {
        setLoadingSessions(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  // ── Load results for active session ──────────────────────────────────────

  useEffect(() => {
    if (!activeSessionId) return;
    setLoadingResults(true);
    setResults([]);
    setPage(1);
    void (async () => {
      try {
        const data = await listSourcingResults(activeSessionId, {
          action: actionFilter || undefined,
          ats_tier: tierFilter || undefined,
          page: 1,
          page_size: 20,
        });
        setResults(data.items);
        setTotalResults(data.total);
      } catch {
        setError("Failed to load candidates.");
      } finally {
        setLoadingResults(false);
      }
    })();
  }, [activeSessionId, actionFilter, tierFilter]);

  // ── Poll active session while running ────────────────────────────────────

  const handlePollUpdate = useCallback(
    (status: SessionStatusResponse) => {
      setSessionStatus(status);
      // Update sessions list
      setSessions((prev) =>
        prev.map((s) =>
          s.id === status.session_id
            ? { ...s, status: status.status, total_results: status.total_results }
            : s,
        ),
      );
      // When complete, re-fetch results
      if (status.status === "complete" && activeSessionId) {
        void listSourcingResults(activeSessionId, {
          action: actionFilter || undefined,
          ats_tier: tierFilter || undefined,
          page: 1,
          page_size: 20,
        }).then((data) => {
          setResults(data.items);
          setTotalResults(data.total);
        });
      }
    },
    [activeSessionId, actionFilter, tierFilter],
  );

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? null;
  const isRunning = activeSession?.status === "running" || activeSession?.status === "pending";

  useSessionPoller(
    isRunning ? activeSessionId : null,
    handlePollUpdate,
  );

  // ── Callbacks ─────────────────────────────────────────────────────────────

  const handleSessionStarted = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId);
    setSessions((prev) => [
      {
        id: sessionId,
        organization_id: "",
        job_id: null,
        created_by: null,
        status: "pending",
        providers_used: ["airis", "naukri_stub"],
        total_results: 0,
        error_detail: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      ...prev,
    ]);
  }, []);

  const handleResultUpdate = useCallback((updated: SourcingResult) => {
    setResults((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
  }, []);

  // ── Access guard ───────────────────────────────────────────────────────────

  if (role !== "admin" && role !== "recruiter") {
    return <p className="text-sm text-slate-600">Only admins and recruiters can access the sourcing workspace.</p>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-[#FF5A1F]" />
            AI Candidate Sourcing
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Discover candidates from AIRIS and external sources using AI search
          </p>
        </div>
        <button
          onClick={() => setDialogOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#FF5A1F] text-white text-sm font-medium hover:bg-[#e04f1a] transition-colors"
        >
          <Search className="h-4 w-4" />
          Start New Session
        </button>
      </div>

      {/* Running banner */}
      {isRunning && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Sourcing in progress… {sessionStatus?.total_results ? `${sessionStatus.total_results} candidates found so far` : ""}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex gap-6">
        {/* Sidebar: Session list */}
        <aside className="w-56 flex-shrink-0">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Sessions</h2>
          {loadingSessions ? (
            <p className="text-xs text-gray-400">Loading…</p>
          ) : sessions.length === 0 ? (
            <p className="text-xs text-gray-400">No sessions yet. Start one above.</p>
          ) : (
            <ul className="space-y-1">
              {sessions.map((s) => (
                <li key={s.id}>
                  <button
                    onClick={() => setActiveSessionId(s.id)}
                    className={`w-full text-left rounded-lg px-3 py-2 text-xs transition-colors ${
                      s.id === activeSessionId
                        ? "bg-[#FF5A1F]/10 text-[#FF5A1F] font-semibold"
                        : "hover:bg-gray-100 text-gray-700"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="truncate">{new Date(s.created_at).toLocaleDateString()}</span>
                      <StatusChip status={s.status} />
                    </div>
                    <div className="text-gray-400 mt-0.5">{s.total_results} candidates</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* Filters */}
          <div className="flex flex-wrap gap-3 mb-4">
            {/* Action filter */}
            <div className="flex gap-1">
              {ACTION_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setActionFilter(f.value)}
                  className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors ${
                    actionFilter === f.value
                      ? "bg-[#FF5A1F] text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* Tier filter */}
            <select
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
              className="text-xs rounded-lg border border-gray-200 px-2 py-1.5 text-gray-700 focus:outline-none focus:ring-2 focus:ring-[#FF5A1F]/30"
            >
              <option value="">All tiers</option>
              {TIER_FILTERS.filter(Boolean).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {/* Results grid */}
          {!activeSessionId ? (
            <EmptyState message="Start a new sourcing session to discover candidates." />
          ) : loadingResults ? (
            <div className="flex items-center justify-center h-40">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : results.length === 0 ? (
            <EmptyState message="No candidates found. Try adjusting your filters." />
          ) : (
            <>
              <p className="text-xs text-gray-500 mb-3">{totalResults} candidates found</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {results.map((r) => (
                  <CandidateCard
                    key={r.id}
                    result={r}
                    sessionId={activeSessionId}
                    onActionUpdate={handleResultUpdate}
                  />
                ))}
              </div>
              {totalResults > results.length && (
                <div className="mt-4 text-center">
                  <button
                    onClick={() => {
                      const nextPage = page + 1;
                      setPage(nextPage);
                      void listSourcingResults(activeSessionId, {
                        action: actionFilter || undefined,
                        ats_tier: tierFilter || undefined,
                        page: nextPage,
                        page_size: 20,
                      }).then((data) => setResults((prev) => [...prev, ...data.items]));
                    }}
                    className="text-sm text-[#FF5A1F] hover:underline"
                  >
                    Load more
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <StartSessionDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onStarted={handleSessionStarted}
      />
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending:  "bg-gray-100 text-gray-500",
    running:  "bg-amber-100 text-amber-700",
    complete: "bg-emerald-100 text-emerald-700",
    failed:   "bg-red-100 text-red-700",
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${styles[status] ?? styles.pending}`}>
      {status}
    </span>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-40 text-gray-400 space-y-2">
      <Search className="h-8 w-8 opacity-40" />
      <p className="text-sm">{message}</p>
    </div>
  );
}
