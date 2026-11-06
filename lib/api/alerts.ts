import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { AlertsResponse, AlertItem, AlertUpdateRequest } from "@/types/alerts";

export async function listAlerts(
  params?: {
    severity?: string;
    acknowledged?: boolean;
  },
  signal?: AbortSignal
): Promise<AlertsResponse> {
  const queryParams: Record<string, string | boolean> = {};
  if (params?.severity && params.severity !== "all") {
    queryParams.severity = params.severity;
  }
  if (params?.acknowledged !== undefined) {
    queryParams.acknowledged = params.acknowledged;
  }

  return apiRequest<AlertsResponse>(ENDPOINTS.ALERTS, {
    params: Object.keys(queryParams).length > 0 ? queryParams : undefined,
    signal,
  });
}

export async function updateAlert(
  id: string,
  update: AlertUpdateRequest,
  signal?: AbortSignal
): Promise<AlertItem> {
  return apiRequest<AlertItem>(ENDPOINTS.ALERT_BY_ID(id), {
    method: "PATCH",
    body: update as unknown as Record<string, unknown>,
    signal,
  });
}
