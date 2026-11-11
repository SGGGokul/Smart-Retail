import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { AnalyticsSummaryResponse } from "@/types/dashboard";
import type {
  AnalyticsTrafficResponse,
  AnalyticsDwellResponse,
} from "@/types/analytics";
import type { AlertsResponse } from "@/types/alerts";

export interface ReportBundle {
  summary: AnalyticsSummaryResponse;
  traffic: AnalyticsTrafficResponse;
  dwell: AnalyticsDwellResponse;
  alerts: AlertsResponse;
}

/**
 * Gathers aggregate telemetry across backend endpoints for the reports module.
 */
export async function getReportBundle(
  range: "today" | "7d" | "30d" = "7d",
  signal?: AbortSignal
): Promise<ReportBundle> {
  const [summary, traffic, dwell, alerts] = await Promise.all([
    apiRequest<AnalyticsSummaryResponse>(ENDPOINTS.ANALYTICS_SUMMARY, { signal }),
    apiRequest<AnalyticsTrafficResponse>(ENDPOINTS.ANALYTICS_TRAFFIC, {
      params: { range },
      signal,
    }),
    apiRequest<AnalyticsDwellResponse>(ENDPOINTS.ANALYTICS_DWELL_TIME, { signal }),
    apiRequest<AlertsResponse>(ENDPOINTS.ALERTS, { signal }),
  ]);

  return { summary, traffic, dwell, alerts };
}
