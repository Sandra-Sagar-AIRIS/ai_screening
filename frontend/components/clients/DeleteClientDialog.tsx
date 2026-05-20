"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { Client } from "@/lib/api/types";

type Props = {
  client: Client;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
};

export function DeleteClientDialog({ client, onConfirm, onCancel }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    setError(null);
    setLoading(true);
    try {
      await onConfirm();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to archive client.");
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-600">
        Are you sure you want to archive{" "}
        <span className="font-semibold text-gray-900">{client.name}</span>?
      </p>
      <p className="text-sm text-gray-500">
        The client will be hidden from all views but its data will be preserved.
        This action can be reversed by an administrator.
      </p>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
        <Button
          type="button"
          onClick={handleDelete}
          disabled={loading}
          className="bg-red-600 hover:bg-red-700 text-white"
        >
          {loading ? "Archiving…" : "Archive Client"}
        </Button>
      </div>
    </div>
  );
}
