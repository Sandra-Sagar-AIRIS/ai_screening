"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AssignVendorModal } from "@/components/AssignVendorModal";
import { CandidateTable } from "@/components/CandidateTable";
import { VendorList } from "@/components/VendorList";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, formatApiErrorForUser } from "@/lib/api/client";
import {
  assignVendorToJob,
  getJobById,
  getJobCandidates,
  getJobVendors,
  invalidateVendorListCache,
  removeVendorFromJob,
} from "@/lib/api";
import type { Job, JobCandidateRow, JobVendorAssignment } from "@/lib/api/types";
import { hasPermission } from "@/lib/rbac";
import { useAuthStore } from "@/store/auth-store";

const JOBS_UPDATE = "jobs:update";

export default function RecruiterJobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params.id;
  const permissions = useAuthStore((state) => state.permissions);

  const canManageVendors = hasPermission(permissions, JOBS_UPDATE);

  const [job, setJob] = useState<Job | null>(null);
  const [vendors, setVendors] = useState<JobVendorAssignment[]>([]);
  const [candidates, setCandidates] = useState<JobCandidateRow[]>([]);

  const [loadingJob, setLoadingJob] = useState(true);
  const [loadingVendors, setLoadingVendors] = useState(true);
  const [loadingCandidates, setLoadingCandidates] = useState(true);

  const [jobError, setJobError] = useState<string | null>(null);
  const [vendorsError, setVendorsError] = useState<string | null>(null);
  const [candidatesError, setCandidatesError] = useState<string | null>(null);

  const [assignOpen, setAssignOpen] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [assignInFlight, setAssignInFlight] = useState(false);

  useEffect(() => {
    if (!jobId) {
      return;
    }
    let cancelled = false;

    void (async () => {
      setJobError(null);
      setVendorsError(null);
      setCandidatesError(null);
      setLoadingJob(true);
      setLoadingVendors(true);
      setLoadingCandidates(true);
      setJob(null);
      setVendors([]);
      setCandidates([]);

      try {
        const j = await getJobById(jobId);
        if (cancelled) {
          return;
        }
        setJob(j);
      } catch (err) {
        if (cancelled) {
          return;
        }
        setJobError(formatApiErrorForUser(err));
        setLoadingJob(false);
        setLoadingVendors(false);
        setLoadingCandidates(false);
        return;
      } finally {
        if (!cancelled) {
          setLoadingJob(false);
        }
      }

      const results = await Promise.allSettled([getJobVendors(jobId), getJobCandidates(jobId)]);
      if (cancelled) {
        return;
      }

      const [vRes, cRes] = results;
      if (vRes.status === "fulfilled") {
        setVendors(vRes.value);
      } else {
        setVendors([]);
        setVendorsError(formatApiErrorForUser(vRes.reason));
      }
      setLoadingVendors(false);

      if (cRes.status === "fulfilled") {
        setCandidates(cRes.value);
      } else {
        setCandidates([]);
        setCandidatesError(formatApiErrorForUser(cRes.reason));
      }
      setLoadingCandidates(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [jobId]);

  const handleAssignVendor = useCallback(
    async (vendorId: string, email: string) => {
      if (!jobId) {
        return;
      }
      const previous = vendors;
      if (previous.some((v) => v.vendor_id === vendorId)) {
        return;
      }
      setAssignInFlight(true);
      setVendors((v) => [...v, { vendor_id: vendorId, email }]);
      try {
        await assignVendorToJob(jobId, vendorId);
        invalidateVendorListCache();
      } catch (err) {
        setVendors(previous);
        throw err;
      } finally {
        setAssignInFlight(false);
      }
    },
    [jobId, vendors]
  );

  const handleRemoveVendor = useCallback(
    async (vendorId: string) => {
      if (!jobId) {
        return;
      }
      const previous = vendors;
      setRemovingId(vendorId);
      setVendors((v) => v.filter((x) => x.vendor_id !== vendorId));
      try {
        await removeVendorFromJob(jobId, vendorId);
        invalidateVendorListCache();
      } catch (err) {
        setVendors(previous);
        setVendorsError(err instanceof ApiError ? formatApiErrorForUser(err) : "Unable to remove vendor.");
      } finally {
        setRemovingId(null);
      }
    },
    [jobId, vendors]
  );

  if (!jobId) {
    return <p className="text-sm text-red-600">Missing job id.</p>;
  }

  if (loadingJob) {
    return <p className="text-sm text-slate-600">Loading job…</p>;
  }

  if (jobError && !job) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-red-600">{jobError}</p>
        <Link className="text-sm text-slate-900 underline" href="/dashboard/jobs">
          Back to jobs
        </Link>
      </div>
    );
  }

  if (!job) {
    return null;
  }

  const partialWarning =
    vendorsError || candidatesError
      ? [
          vendorsError ? `Vendors: ${vendorsError}` : null,
          candidatesError ? `Candidates: ${candidatesError}` : null,
        ]
          .filter(Boolean)
          .join(" ")
      : null;

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold text-slate-900">{job.title}</h1>
        <Link className="text-sm text-slate-700 underline decoration-slate-300 underline-offset-2" href="/dashboard/jobs">
          ← All jobs
        </Link>
      </div>

      {partialWarning ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Some data could not be loaded. Showing partial results. {partialWarning}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Job information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            <span className="font-medium text-slate-800">Status:</span>{" "}
            <span className="capitalize text-slate-700">{job.status}</span>
          </p>
          {job.description ? (
            <p>
              <span className="font-medium text-slate-800">Description:</span>{" "}
              <span className="whitespace-pre-wrap text-slate-700">{job.description}</span>
            </p>
          ) : (
            <p className="text-slate-600">No description.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 space-y-0">
          <CardTitle>Assigned vendors</CardTitle>
          {canManageVendors ? (
            <Button
              type="button"
              className="h-8 px-3 text-xs"
              onClick={() => setAssignOpen(true)}
              disabled={assignInFlight || removingId !== null}
            >
              + Assign vendor
            </Button>
          ) : null}
        </CardHeader>
        <CardContent>
          {loadingVendors ? <p className="text-sm text-slate-600">Loading vendors…</p> : null}
          {!loadingVendors ? (
            <VendorList
              vendors={vendors}
              canRemove={canManageVendors}
              lockActions={assignInFlight}
              removingId={removingId}
              onRemove={handleRemoveVendor}
            />
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Candidates</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingCandidates ? <p className="text-sm text-slate-600">Loading candidates…</p> : null}
          {!loadingCandidates ? <CandidateTable rows={candidates} /> : null}
        </CardContent>
      </Card>

      {canManageVendors ? (
        <AssignVendorModal
          open={assignOpen}
          assignedVendorIds={vendors.map((v) => v.vendor_id)}
          onClose={() => setAssignOpen(false)}
          onAssign={handleAssignVendor}
        />
      ) : null}
    </section>
  );
}
