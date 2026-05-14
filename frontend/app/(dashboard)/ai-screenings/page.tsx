"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Brain,
  Plus,
  RefreshCw,
  Search,
  ChevronRight,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  Loader2,
  User,
  Briefcase,
  BarChart3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listScreenings } from "@/lib/api/ai_screening";
import type { AIScreeningListItem, ScreeningStatus, ScreeningRecommendation } from "@/lib/api/types";
import { cn } from "@/lib/utils";

// ── Status helpers ────────────────────────────────────────────────────────────

function statusLabel(status: ScreeningStatus): string {
  return {
    pending: "Pending",
    generating_questions: "Generating Questions",
    questions_ready: "Questions Ready",
    evaluating: "Evaluating",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
  }[status] ?? status;
}

function StatusBadge({ status }: { status: ScreeningStatus }) {
  const config: Record<ScreeningStatus, { color: string; icon: React.ElementType }> = {
    pending: { color: "bg-gray-100 text-gray-700", icon: Clock },
    generating_questions: { color: "bg-blue-100 text-blue-700", icon: Loader2 },
    questions_ready: { color: "bg-yellow-100 text-yellow-700", icon: Clock },
    evaluating: { color: "bg-purple-100 text-purple-700", icon: Loader2 },
    completed: { color: "bg-green-100 text-green-700", icon: CheckCircle2 },
    failed: { color: "bg-red-100 text-red-700", icon: XCircle },
    cancelled: { color: "bg-gray-100 text-gray-500", icon: XCircle },
  };
  const { color, icon: Icon } = config[status] ?? { color: "bg-gray-100 text-gray-600", icon: AlertCircle };
  const spinning = status === "generating_questions" || status === "evaluating";

  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium", color)}>
      <Icon className={cn("w-3 h-3", spinning && "animate-spin")} />
      {statusLabel(status)}
    </span>
  );
}

function RecommendationBadge({ rec }: { rec: ScreeningRecommendation | null }) {
  if (!rec) return <span className="text-gray-400 text-xs">—</span>;
  const config: Record<ScreeningRecommendation, { color: string; label: string }> = {
    strong_proceed: { color: "bg-emerald-100 text-emerald-800", label: "Strong Proceed" },
    proceed: { color: "bg-green-100 text-green-700", label: "Proceed" },
    needs_manual_review: { color: "bg-yellow-100 text-yellow-700", label: "Manual Review" },
    weak_match: { color: "bg-orange-100 text-orange-700", label: "Weak Match" },
    reject_recommendation: { color: "bg-red-100 text-red-700", label: "Reject" },
  };
  const { color, label } = config[rec];
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium", color)}>
      {label}
    </span>
  );
}

function ScoreBar({ score, label }: { score: number | null; label: string }) {
  if (score === null) return <span className="text-gray-400 text-sm">—</span>;
  const pct = Math.min(100, Math.max(0, score));
  const color =
    pct >= 75 ? "bg-emerald-500" : pct >= 55 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-medium text-gray-700 tabular-nums w-8 text-right">
        {Math.round(pct)}
      </span>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AIScreeningsPage() {
  const [screenings, setScreenings] = useState<AIScreeningListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await listScreenings({
        status: statusFilter || undefined,
        limit: 100,
      });
      setScreenings(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load screenings");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  // Auto-refresh if any screening is in a transient state
  useEffect(() => {
    const hasTransient = screenings.some((s) =>
      ["pending", "generating_questions", "evaluating"].includes(s.status)
    );
    if (!hasTransient) return;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [screenings, load]);

  const filtered = screenings.filter((s) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (s.candidate_name ?? "").toLowerCase().includes(q) ||
      (s.candidate_email ?? "").toLowerCase().includes(q) ||
      (s.job_title ?? "").toLowerCase().includes(q)
    );
  });

  const stats = {
    total: screenings.length,
    completed: screenings.filter((s) => s.status === "completed").length,
    inProgress: screenings.filter((s) =>
      ["pending", "generating_questions", "questions_ready", "evaluating"].includes(s.status)
    ).length,
    proceed: screenings.filter((s) =>
      ["strong_proceed", "proceed"].includes(s.recommendation ?? "")
    ).length,
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-orange-100 flex items-center justify-center">
              <Brain className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">AI Screenings</h1>
              <p className="text-sm text-gray-500">AI-assisted candidate pre-screening</p>
            </div>
          </div>
          <Button
            className="bg-orange-600 hover:bg-orange-700 text-white gap-2"
            onClick={() => {/* handled by candidate page — screenings are started from there */
              window.location.href = "/candidates";
            }}
          >
            <Plus className="w-4 h-4" />
            New Screening
          </Button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Total Screenings", value: stats.total, icon: BarChart3, color: "text-gray-600" },
            { label: "Completed", value: stats.completed, icon: CheckCircle2, color: "text-green-600" },
            { label: "In Progress", value: stats.inProgress, icon: Loader2, color: "text-blue-600" },
            { label: "Recommended to Proceed", value: stats.proceed, icon: CheckCircle2, color: "text-emerald-600" },
          ].map(({ label, value, icon: Icon, color }) => (
            <Card key={label} className="border border-gray-200 shadow-none">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-2 mb-1">
                  <Icon className={cn("w-4 h-4", color)} />
                  <span className="text-xs text-gray-500">{label}</span>
                </div>
                <p className="text-2xl font-bold text-gray-900">{value}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="Search by candidate or job..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9 bg-white border-gray-200"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 px-3 text-sm border border-gray-200 rounded-md bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="questions_ready">Questions Ready</option>
            <option value="evaluating">Evaluating</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
          <Button
            variant="outline"
            size="sm"
            onClick={load}
            className="h-9 gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>

        {/* Table */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-orange-500" />
          </div>
        ) : error ? (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-4">
              <p className="text-red-700 text-sm">{error}</p>
            </CardContent>
          </Card>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <Brain className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">No screenings found</p>
            <p className="text-gray-400 text-sm mt-1">
              Start a screening from a candidate profile to begin AI pre-screening.
            </p>
          </div>
        ) : (
          <Card className="border border-gray-200 shadow-none overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Candidate</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Job</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Score</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">AI Recommendation</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Decision</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Date</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {filtered.map((s) => (
                    <tr
                      key={s.id}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center shrink-0">
                            <User className="w-3.5 h-3.5 text-gray-500" />
                          </div>
                          <div className="min-w-0">
                            <p className="font-medium text-gray-900 truncate">
                              {s.candidate_name ?? "Unknown"}
                            </p>
                            <p className="text-xs text-gray-500 truncate">{s.candidate_email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 text-gray-700">
                          <Briefcase className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                          <span className="truncate max-w-[160px]">
                            {s.job_title ?? <span className="text-gray-400">—</span>}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="capitalize text-gray-700">
                          {s.screening_type.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={s.status} />
                      </td>
                      <td className="px-4 py-3 w-36">
                        <ScoreBar score={s.overall_score} label="Overall" />
                      </td>
                      <td className="px-4 py-3">
                        <RecommendationBadge rec={s.recommendation} />
                      </td>
                      <td className="px-4 py-3">
                        {s.recruiter_decision ? (
                          <span className="capitalize text-gray-700">
                            {s.recruiter_decision}
                          </span>
                        ) : (
                          <span className="text-gray-400 text-xs">Pending</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                        {new Date(s.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <Link href={`/ai-screenings/${s.id}`}>
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                            <ChevronRight className="w-4 h-4" />
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
