"use client";

import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { getPipelines } from "@/lib/api/pipeline";
import { PIPELINE_UPDATE_PERMISSION, hasPermission } from "@/lib/rbac";
import type { Pipeline, PipelineStage } from "@/lib/api/types";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";

const STAGES: PipelineStage[] = ["applied", "screening", "interview", "offer", "placed", "rejected"];

export default function PipelinePage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [error, setError] = useState<string | null>(null);
  const permissions = useAuthStore((state) => state.permissions);

  useEffect(() => {
    async function loadData() {
      try {
        const data = await getPipelines(200, 0);
        setPipelines(data);
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else {
          setError("Unable to load pipeline");
        }
      }
    }
    loadData();
  }, []);

  const grouped = useMemo(() => {
    return STAGES.reduce<Record<string, Pipeline[]>>((acc, stage) => {
      acc[stage] = pipelines.filter((p) => p.stage === stage);
      return acc;
    }, {});
  }, [pipelines]);

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Pipeline</h1>
        {hasPermission(permissions, PIPELINE_UPDATE_PERMISSION) ? <Button>Move candidate</Button> : null}
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {STAGES.map((stage) => (
          <Card key={stage}>
            <CardHeader>
              <CardTitle className="capitalize">{stage}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {grouped[stage]?.length ? (
                grouped[stage].map((item) => (
                  <div key={item.id} className="rounded-md border border-slate-200 p-2 text-sm">
                    <p><span className="font-medium">Candidate:</span> {item.candidate_id}</p>
                    <p><span className="font-medium">Job:</span> {item.job_id}</p>
                    <p><span className="font-medium">Status:</span> {item.status}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">No candidates in this stage.</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
