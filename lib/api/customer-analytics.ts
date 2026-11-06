import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type {
  AnalyticsTrafficResponse,
  AnalyticsDwellResponse,
  AnalyticsQueuesResponse,
} from "@/types/analytics";

/**
 * Retrieves daily and hourly customer traffic counts.
 * GET /api/v1/analytics/traffic
 */
export async function getCustomerTraffic(
  range?: "today" | "7d" | "30d" | string,
  signal?: AbortSignal
): Promise<AnalyticsTrafficResponse> {
  return apiRequest<AnalyticsTrafficResponse>(ENDPOINTS.ANALYTICS_TRAFFIC, {
    params: range ? { range } : undefined,
    signal,
  });
}

/**
 * Retrieves customer dwell time per store department/section.
 * GET /api/v1/analytics/dwell-time
 */
export async function getCustomerDwellTime(signal?: AbortSignal): Promise<AnalyticsDwellResponse> {
  return apiRequest<AnalyticsDwellResponse>(ENDPOINTS.ANALYTICS_DWELL_TIME, { signal });
}

/**
 * Retrieves active queue metrics across all store checkouts.
 * GET /api/v1/analytics/queues
 */
export async function getCheckoutQueues(signal?: AbortSignal): Promise<AnalyticsQueuesResponse> {
  return apiRequest<AnalyticsQueuesResponse>(ENDPOINTS.ANALYTICS_QUEUES, { signal });
}
