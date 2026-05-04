"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { submitCandidate } from "@/lib/api/vendor";
import { CandidateForm } from "@/components/vendor/candidate-form";
import type { CandidateCreatePayload } from "@/lib/api/types";

export default function SubmitCandidatePage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit(payload: CandidateCreatePayload) {
    if (!params.jobId) {
      setError("Missing job id.");
      return;
    }
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);
    try {
      await submitCandidate(params.jobId, payload);
      setSuccess("Candidate submitted successfully.");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to submit candidate.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Submit Candidate</h1>
        <Button onClick={() => router.push("/vendor/jobs")} variant="outline">
          Back to My Jobs
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Job ID: {params.jobId ?? "N/A"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {success ? (
            <div className="space-y-2">
              <p className="text-sm text-emerald-700">{success}</p>
              <Link className="text-sm text-blue-600 hover:underline" href="/vendor/jobs">
                Return to My Jobs
              </Link>
            </div>
          ) : null}
          <CandidateForm isSubmitting={isSubmitting} onSubmit={handleSubmit} />
        </CardContent>
      </Card>
    </section>
  );
}

