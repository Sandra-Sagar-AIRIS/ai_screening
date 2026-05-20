import { apiRequest } from "@/lib/api/client";
import type { Client } from "@/lib/api/types";

export async function listClients(limit = 200, offset = 0): Promise<Client[]> {
  return apiRequest<Client[]>(`/clients?limit=${limit}&offset=${offset}`);
}

/** Fetch all clients (paginated) for dropdowns and filters. */
export async function listAllClients(): Promise<Client[]> {
  const pageSize = 200;
  let offset = 0;
  const all: Client[] = [];
  while (true) {
    const batch = await listClients(pageSize, offset);
    all.push(...batch);
    if (batch.length < pageSize) {
      break;
    }
    offset += pageSize;
  }
  return all;
}
