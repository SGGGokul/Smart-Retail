import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { AnalyticsSummaryResponse } from "@/types/dashboard";
import type {
  AnalyticsTrafficResponse,
  AnalyticsDwellResponse,
  AnalyticsQueuesResponse,
} from "@/types/analytics";

export async function getSummary(signal?: AbortSignal): Promise<AnalyticsSummaryResponse> {
  return apiRequest<AnalyticsSummaryResponse>(ENDPOINTS.ANALYTICS_SUMMARY, { signal });
}

export async function getTraffic(
  range?: "today" | "7d" | "30d" | string,
  signal?: AbortSignal
): Promise<AnalyticsTrafficResponse> {
  return apiRequest<AnalyticsTrafficResponse>(ENDPOINTS.ANALYTICS_TRAFFIC, {
    params: range ? { range } : undefined,
    signal,
  });
}

export async function getDwellTime(signal?: AbortSignal): Promise<AnalyticsDwellResponse> {
  return apiRequest<AnalyticsDwellResponse>(ENDPOINTS.ANALYTICS_DWELL_TIME, { signal });
}

export async function getQueues(signal?: AbortSignal): Promise<AnalyticsQueuesResponse> {
  return apiRequest<AnalyticsQueuesResponse>(ENDPOINTS.ANALYTICS_QUEUES, { signal });
}
