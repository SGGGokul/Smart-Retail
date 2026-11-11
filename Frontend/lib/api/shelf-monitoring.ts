import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { ShelvesResponse, ShelfItem, ShelfMetricsResponse } from "@/types/shelves";
import type { EventTimelineResponse } from "@/types/events";

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
 * Get aggregated shelf metrics (occupancy, empty slots, pickups, returns, interactions).
 * GET /api/v1/shelves/metrics
 */
export async function getShelfMetrics(signal?: AbortSignal): Promise<ShelfMetricsResponse> {
  return apiRequest<ShelfMetricsResponse>(ENDPOINTS.SHELVES_METRICS, { signal });
}

/**
 * Get unified retail events timeline with optional filters.
 * GET /api/v1/events/timeline
 */
export async function getRetailEventsTimeline(
  params?: {
    shelf_id?: string;
    visitor_id?: string;
    event_type?: string;
    confirmation_status?: string;
    limit?: number;
  },
  signal?: AbortSignal
): Promise<EventTimelineResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.shelf_id) queryParams.shelf_id = params.shelf_id;
  if (params?.visitor_id) queryParams.visitor_id = params.visitor_id;
  if (params?.event_type) queryParams.event_type = params.event_type;
  if (params?.confirmation_status) queryParams.confirmation_status = params.confirmation_status;
  if (params?.limit) queryParams.limit = String(params.limit);

  return apiRequest<EventTimelineResponse>(ENDPOINTS.EVENTS_TIMELINE, {
    params: Object.keys(queryParams).length > 0 ? queryParams : undefined,
    signal,
  });
}

/**
 * Get single shelf status if supported by backend.
 */
export async function getShelfById(id: string, signal?: AbortSignal): Promise<ShelfItem> {
  return apiRequest<ShelfItem>(`${ENDPOINTS.SHELVES}/${encodeURIComponent(id)}`, { signal });
}
