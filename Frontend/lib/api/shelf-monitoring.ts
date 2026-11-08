import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { ShelvesResponse, ShelfItem } from "@/types/shelves";

/**
 * Lists all monitored retail shelf zones and their stock levels.
 * GET /api/v1/shelves
 */
export async function listShelves(
  status?: "all" | "low" | "critical",
  signal?: AbortSignal
): Promise<ShelvesResponse> {
  const params: Record<string, string> = {};
  if (status && status !== "all") {
    params.status = status;
  }
  return apiRequest<ShelvesResponse>(ENDPOINTS.SHELVES, {
    params: Object.keys(params).length > 0 ? params : undefined,
    signal,
  });
}

/**
 * Get single shelf status if supported by backend.
 */
export async function getShelfById(id: string, signal?: AbortSignal): Promise<ShelfItem> {
  return apiRequest<ShelfItem>(`${ENDPOINTS.SHELVES}/${encodeURIComponent(id)}`, { signal });
}
