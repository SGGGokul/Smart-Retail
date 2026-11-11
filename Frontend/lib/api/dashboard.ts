import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { AnalyticsSummaryResponse } from "@/types/dashboard";
import type { AnalyticsTrafficResponse } from "@/types/analytics";
import type { ShelvesResponse } from "@/types/shelves";
import type { AlertsResponse } from "@/types/alerts";

/**
 * Returns aggregate KPI metrics for the store overview dashboard.
 * GET /api/v1/analytics/summary
 */
export async function getDashboardSummary(signal?: AbortSignal): Promise<AnalyticsSummaryResponse> {
  return apiRequest<AnalyticsSummaryResponse>(ENDPOINTS.ANALYTICS_SUMMARY, { signal });
}

/**
 * Retrieves daily & hourly traffic for the dashboard charts.
 * GET /api/v1/analytics/traffic?range=...
 */
export async function getDashboardTraffic(
  range: "today" | "7d" | "30d" = "7d",
  signal?: AbortSignal
): Promise<AnalyticsTrafficResponse> {
  return apiRequest<AnalyticsTrafficResponse>(ENDPOINTS.ANALYTICS_TRAFFIC, {
    params: { range },
    signal,
  });
}

/**
 * Retrieves latest alerts to populate the dashboard recent incident feed.
 * GET /api/v1/alerts
 */
export async function getDashboardEvents(signal?: AbortSignal): Promise<AlertsResponse> {
  return apiRequest<AlertsResponse>(ENDPOINTS.ALERTS, { signal });
}

/**
 * Retrieves shelf health for the dashboard aisle status summary.
 * GET /api/v1/shelves
 */
export async function getDashboardShelves(signal?: AbortSignal): Promise<ShelvesResponse> {
  return apiRequest<ShelvesResponse>(ENDPOINTS.SHELVES, { signal });
}
