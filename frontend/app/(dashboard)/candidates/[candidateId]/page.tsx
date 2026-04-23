"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api/client";
import { getCandidateById } from "@/lib/api/candidates";
import type { Candidate } from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function CandidateDetailPage() {
  const params = useParams<{ candidateId: string }>();
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.candidateId) {
      return;
    }
    async function loadData() {
      try {
        const data = await getCandidateById(params.candidateId);
        setCandidate(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load candidate details");
        }
      }
    }
    loadData();
  }, [params.candidateId]);

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (!candidate) {
    return <p className="text-sm text-slate-600">Loading candidate...</p>;
  }

  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Candidate Detail</h1>
      <Card>
        <CardHeader>
          <CardTitle>{candidate.first_name} {candidate.last_name}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><span className="font-medium">Email:</span> {candidate.email}</p>
          <p><span className="font-medium">Phone:</span> {candidate.phone ?? "-"}</p>
          <p><span className="font-medium">Location:</span> {candidate.location ?? "-"}</p>
          <p><span className="font-medium">Experience:</span> {candidate.experience_summary ?? "-"}</p>
          <p><span className="font-medium">Education:</span> {candidate.education ?? "-"}</p>
          <p><span className="font-medium">Notes:</span> {candidate.notes ?? "-"}</p>
        </CardContent>
      </Card>
    </section>
  );
}
