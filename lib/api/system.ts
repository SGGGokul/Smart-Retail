import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type { HealthResponse } from "@/types/system";

/**
 * Verifies backend service liveness and database/model dependency health.
 * GET /health
 */
export async function checkHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>(ENDPOINTS.HEALTH, { signal });
}
