"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getJobById } from "@/lib/api/jobs";
import type { Job } from "@/lib/api/types";

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.jobId) {
      return;
    }
    async function loadData() {
      try {
        const data = await getJobById(params.jobId);
        setJob(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load job details");
        }
      }
    }
    loadData();
  }, [params.jobId]);

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (!job) {
    return <p className="text-sm text-slate-600">Loading job...</p>;
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Job Detail</h1>
      <Card>
        <CardHeader>
          <CardTitle>{job.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><span className="font-medium">Status:</span> {job.status}</p>
          <p><span className="font-medium">Client ID:</span> {job.client_id}</p>
          <p><span className="font-medium">Description:</span> {job.description ?? "-"}</p>
        </CardContent>
      </Card>
    </section>
  );
}
