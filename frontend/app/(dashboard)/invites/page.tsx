"use client";

import { FormEvent, useEffect, useState, useMemo } from "react";
import { 
  Search, Send, MoreHorizontal, ChevronLeft, ChevronRight, 
  Mail, CheckCircle2, Clock, CalendarX2, RefreshCw, AlertCircle
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { getInvites, resendInvite, createInvite } from "@/lib/api/invites";
import { listOrganizationRoles } from "@/lib/api/roles";
import type { InviteListItem } from "@/lib/api/types";

// F-INV-05: derive display status — server-side status is the source of truth,
// but client can lazily infer 'expired' for 'sent'/'opened' past their expiry.
function getInviteStatus(invite: InviteListItem): string {
  const s = invite.status.toLowerCase();
  if (s === "accepted" || s === "expired") return s;
  if ((s === "sent" || s === "opened") && invite.expires_at && new Date(invite.expires_at) < new Date()) {
    return "expired";
  }
  return s;
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  let className = "bg-slate-100 text-slate-500";
  let dotColor = "bg-slate-400";

  if (normalized === "accepted") {
    className = "bg-emerald-50 text-emerald-600 border border-emerald-100";
    dotColor = "bg-emerald-500";
  } else if (normalized === "opened") {
    className = "bg-blue-50 text-blue-600 border border-blue-100";
    dotColor = "bg-blue-500";
  } else if (normalized === "sent") {
    className = "bg-amber-50 text-amber-600 border border-amber-100";
    dotColor = "bg-amber-500";
  } else if (normalized === "expired") {
    className = "bg-red-50 text-red-600 border border-red-100";
    dotColor = "bg-red-500";
  }

  return (
    <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold inline-flex items-center gap-1.5 tracking-wider uppercase ${className}`}>
      <div className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      {status}
    </span>
  );
}

function StatCard({ title, value, subtitle }: { title: string, value: number | string, subtitle: string }) {
  return (
    <div className="rounded-[16px] shadow-[0_2px_8px_rgba(0,0,0,0.02)] bg-white p-4 border border-slate-100/80 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] hover:border-slate-200 transition-all duration-300 group cursor-default">
      <div className="mb-2">
        <p className="text-[13px] font-bold text-slate-500 group-hover:text-slate-700 transition-colors duration-300">{title}</p>
      </div>
      <p className="text-[24px] leading-none font-bold text-slate-900 group-hover:text-[#FF5A1F] transition-colors duration-300">{value}</p>
      <p className="text-[11px] font-medium text-slate-400 mt-1.5">{subtitle}</p>
    </div>
  );
}

export default function InvitesPage() {
  const [invites, setInvites] = useState<InviteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resendingId, setResendingId] = useState<string | null>(null);

  // Form state
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("");
  const [roleChoices, setRoleChoices] = useState<{ key: string; name: string }[]>([]);
  const [loadingRoles, setLoadingRoles] = useState(true);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);

  // Filters & Tabs state
  const [activeTab, setActiveTab] = useState<"all" | "pending">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  useEffect(() => {
    async function loadData() {
      try {
        const [invitesData, rolesData] = await Promise.all([
          getInvites(),
          listOrganizationRoles()
        ]);
        setInvites(invitesData);

        const choices = rolesData
          .filter((r) => r.key !== "admin")
          .map((r) => ({ key: r.key, name: r.name }));
        setRoleChoices(choices);
        const recruiter = choices.find((c) => c.key === "recruiter");
        setRole(recruiter?.key ?? choices[0]?.key ?? "");

      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load data for invites.");
        }
      } finally {
        setLoading(false);
        setLoadingRoles(false);
      }
    }
    void loadData();
  }, []);

  async function onResend(inviteId: string) {
    setError(null);
    setResendingId(inviteId);
    try {
      await resendInvite(inviteId);
      // Success feedback can be handled here if needed
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to resend invite");
      }
    } finally {
      setResendingId(null);
    }
  }

  async function onCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFormSuccess(null);

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      setFormError("Please enter an email address.");
      return;
    }
    if (!role) {
      setFormError("Select a role.");
      return;
    }

    setCreating(true);
    try {
      await createInvite({ email: normalizedEmail, role, expires_in_days: 7 });
      setFormSuccess("Invite sent successfully");
      setEmail("");
      const recruiter = roleChoices.find((c) => c.key === "recruiter");
      setRole(recruiter?.key ?? roleChoices[0]?.key ?? "");
      
      // Refresh invites
      const data = await getInvites();
      setInvites(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("Unable to create invite. Please try again.");
      }
    } finally {
      setCreating(false);
      setTimeout(() => { setFormSuccess(null); }, 3000);
    }
  }

  const totalInvites = invites.length;
  const acceptedInvites = invites.filter(i => getInviteStatus(i) === "accepted").length;
  // F-INV-05: 'pending' tab covers both 'sent' and 'opened' (not yet terminal)
  const pendingInvites = invites.filter(i => ["sent", "opened"].includes(getInviteStatus(i))).length;
  const expiredInvites = invites.filter(i => getInviteStatus(i) === "expired").length;

  const acceptanceRate = totalInvites ? Math.round((acceptedInvites / totalInvites) * 100) : 0;

  const filteredInvites = useMemo(() => {
    return invites.filter(invite => {
      const status = getInviteStatus(invite);
      // F-INV-05: 'pending' tab shows sent + opened (active, not yet terminal)
      if (activeTab === "pending" && !["sent", "opened"].includes(status)) return false;
      if (statusFilter !== "all" && status !== statusFilter) return false;
      if (roleFilter !== "all" && invite.role !== roleFilter) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!invite.email.toLowerCase().includes(q) && !invite.role.toLowerCase().includes(q)) {
          return false;
        }
      }
      return true;
    });
  }, [invites, activeTab, searchQuery, statusFilter, roleFilter]);

  const totalPages = Math.ceil(filteredInvites.length / itemsPerPage) || 1;
  const paginatedInvites = filteredInvites.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  const uniqueRoles = Array.from(new Set(invites.map(i => i.role)));

  return (
    <section className="space-y-6 pb-12 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Invites</h1>
          <p className="text-[13px] font-medium text-slate-500 mt-1">Create, manage and track invitations for your organization.</p>
        </div>
      </div>

      {error ? (
        <div className="flex items-start gap-2 rounded-xl border border-red-100 bg-red-50 p-4">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
          <p className="text-sm font-medium text-red-700">{error}</p>
        </div>
      ) : null}

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard 
          title="Total Invites" 
          value={loading ? "…" : totalInvites} 
          subtitle="All time" 
        />
        <StatCard 
          title="Accepted" 
          value={loading ? "…" : acceptedInvites} 
          subtitle={`${acceptanceRate}% acceptance rate`} 
        />
        <StatCard 
          title="Pending" 
          value={loading ? "…" : pendingInvites} 
          subtitle="Awaiting response" 
        />
        <StatCard 
          title="Expired" 
          value={loading ? "…" : expiredInvites} 
          subtitle="Last 30 days" 
        />
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200/60 px-2 mt-8">
        <div className="flex space-x-8">
          <button
            onClick={() => { setActiveTab("all"); setCurrentPage(1); }}
            className={`flex items-center gap-2 border-b-[3px] py-3 text-[14px] font-bold transition-colors ${
              activeTab === "all"
                ? "border-[#FF5A1F] text-slate-900"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            All Invites
          </button>
          <button
            onClick={() => { setActiveTab("pending"); setCurrentPage(1); }}
            className={`flex items-center gap-2 border-b-[3px] py-3 text-[14px] font-bold transition-colors ${
              activeTab === "pending"
                ? "border-[#FF5A1F] text-slate-900"
                : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
            }`}
          >
            Pending Invites ({loading ? "…" : pendingInvites})
          </button>
        </div>
      </div>

      <div className="space-y-6">
        {/* Create Invite Form */}
        <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white border border-slate-100/80 p-6">
          <h3 className="text-[15px] font-bold text-slate-900 tracking-tight mb-5">Create New Invite</h3>
          <form onSubmit={onCreateSubmit} className="flex flex-col gap-5 md:flex-row md:items-end">
            <div className="flex-1 space-y-2">
              <label className="text-[12px] font-bold uppercase tracking-wider text-slate-500" htmlFor="invite-email">
                Email
              </label>
              <Input
                id="invite-email"
                type="email"
                placeholder="Enter email address"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="bg-slate-50 border-slate-200 text-[13px] h-11 focus-visible:bg-white focus-visible:ring-2 focus-visible:ring-orange-100 focus-visible:border-orange-300 transition-all rounded-xl shadow-sm"
              />
            </div>
            <div className="flex-1 space-y-2">
              <label className="text-[12px] font-bold uppercase tracking-wider text-slate-500" htmlFor="invite-role">
                Role
              </label>
              <select
                id="invite-role"
                className="flex h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[13px] font-medium text-slate-700 shadow-sm transition-all focus-visible:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-100 focus-visible:border-orange-300 disabled:opacity-50"
                value={role}
                disabled={loadingRoles || roleChoices.length === 0}
                onChange={(event) => setRole(event.target.value)}
              >
                {roleChoices.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-none">
              <Button type="submit" disabled={creating || loadingRoles || !role} className="w-full md:w-auto h-11 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold px-8 shadow-sm transition-all">
                {creating ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                {creating ? "Sending..." : "Send Invite"}
              </Button>
            </div>
          </form>
          {formError ? <p className="mt-4 text-[13px] text-red-600 font-medium">{formError}</p> : null}
          {formSuccess ? <p className="mt-4 text-[13px] text-emerald-600 font-medium">{formSuccess}</p> : null}
        </div>

        {/* Invites List */}
        <div className="rounded-[20px] shadow-[0_2px_12px_rgba(0,0,0,0.02)] bg-white overflow-hidden border border-slate-100/80 flex flex-col">
          <div className="p-6 border-b border-slate-100/80 space-y-5">
            <h3 className="text-[15px] font-bold text-slate-900 tracking-tight">Invites List</h3>
            
            {/* Filters Row */}
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3.5 top-3 h-4 w-4 text-slate-400" />
                <Input 
                  placeholder="Search by email or role..." 
                  className="pl-10 h-10 bg-slate-50 border-slate-200 text-[13px] rounded-xl shadow-sm focus-visible:bg-white focus-visible:ring-2 focus-visible:ring-orange-100 focus-visible:border-orange-300 transition-all"
                  value={searchQuery}
                  onChange={e => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                />
              </div>
              <select
                className="h-10 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-600 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-100 focus-visible:border-orange-300 transition-all sm:w-40"
                value={statusFilter}
                onChange={e => { setStatusFilter(e.target.value); setCurrentPage(1); }}
              >
                <option value="all">All Status</option>
                <option value="sent">Sent</option>
                <option value="opened">Opened</option>
                <option value="accepted">Accepted</option>
                <option value="expired">Expired</option>
              </select>
              <select 
                className="h-10 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-600 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-100 focus-visible:border-orange-300 transition-all sm:w-40"
                value={roleFilter}
                onChange={e => { setRoleFilter(e.target.value); setCurrentPage(1); }}
              >
                <option value="all">All Roles</option>
                {uniqueRoles.map(r => (
                  <option key={r} value={r} className="capitalize">{r}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="w-full overflow-x-auto">
            <table className="w-full text-left whitespace-nowrap">
              <thead className="bg-slate-50/80 border-b border-slate-100/80">
                <tr className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="px-6 py-4">Email</th>
                  <th className="px-6 py-4">Role</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Invited On</th>
                  <th className="px-6 py-4">Opened At</th>
                  <th className="px-6 py-4">Accepted On</th>
                  <th className="px-6 py-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100/80">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-[13px] font-medium text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <RefreshCw className="h-5 w-5 animate-spin text-slate-300" />
                        <span>Loading invites...</span>
                      </div>
                    </td>
                  </tr>
                ) : paginatedInvites.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-[13px] font-medium text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Mail className="h-6 w-6 text-slate-300" />
                        <span>No invites found matching your criteria.</span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  paginatedInvites.map((invite) => {
                    const status = getInviteStatus(invite);
                    const isAccepted = status === "accepted";
                    const dateOptions: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: 'numeric' };
                    const fmtDate = (ts: string | null) =>
                      ts ? new Date(ts).toLocaleString('en-US', dateOptions) : "—";

                    return (
                      <tr key={invite.id} className="hover:bg-slate-50/60 transition-colors group cursor-default">
                        <td className="px-6 py-4 font-medium text-[14px] text-slate-700 group-hover:text-[#FF5A1F] transition-colors">{invite.email}</td>
                        <td className="px-6 py-4 text-[13px] font-medium text-slate-600 capitalize">
                          <span className="bg-slate-100 px-2 py-1 rounded-md">{invite.role}</span>
                        </td>
                        <td className="px-6 py-4">
                          <StatusBadge status={status} />
                        </td>
                        <td className="px-6 py-4 text-[12px] font-medium text-slate-500">
                          {fmtDate(invite.sent_at ?? invite.created_at)}
                        </td>
                        {/* F-INV-05: opened_at timestamp */}
                        <td className="px-6 py-4 text-[12px] font-medium text-slate-500">
                          {fmtDate(invite.opened_at)}
                        </td>
                        {/* F-INV-05: accepted_at timestamp (was incorrectly using created_at) */}
                        <td className="px-6 py-4 text-[12px] font-medium text-slate-500">
                          {isAccepted ? fmtDate(invite.accepted_at) : "—"}
                        </td>
                        <td className="px-6 py-4 text-center">
                          <div className="flex items-center justify-center gap-2">
                            {status !== "accepted" ? (
                              <Button
                                variant="outline"
                                className="h-8 text-[11px] font-bold px-4 text-slate-600 border-slate-200 bg-white hover:bg-slate-50 hover:text-slate-900 rounded-lg uppercase tracking-wider transition-all"
                                onClick={() => onResend(invite.id)}
                                disabled={resendingId === invite.id}
                              >
                                {resendingId === invite.id ? <RefreshCw className="mr-2 h-3 w-3 animate-spin" /> : <Send className="mr-2 h-3 w-3" />}
                                {resendingId === invite.id ? "Resending..." : "Resend"}
                              </Button>
                            ) : null}
                            <Button variant="ghost" className="h-8 w-8 p-0 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 0 && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-end gap-4 p-5 border-t border-slate-100/80 bg-white">
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  className="h-8 w-8 p-0 text-slate-500 bg-white border-slate-200 rounded-lg hover:bg-slate-50"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                {Array.from({ length: totalPages }).map((_, i) => (
                  <Button
                    key={i}
                    variant={currentPage === i + 1 ? "default" : "outline"}
                    className={`h-8 w-8 p-0 text-[13px] font-bold rounded-lg transition-all ${currentPage === i + 1 ? 'bg-[#FF5A1F] hover:bg-[#e04814] text-white border-transparent' : 'text-slate-600 bg-white border-slate-200 hover:bg-slate-50'}`}
                    onClick={() => setCurrentPage(i + 1)}
                  >
                    {i + 1}
                  </Button>
                ))}
                <Button
                  variant="outline"
                  className="h-8 w-8 p-0 text-slate-500 bg-white border-slate-200 rounded-lg hover:bg-slate-50"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
