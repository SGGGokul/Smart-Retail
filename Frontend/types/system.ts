export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  version: string;
  uptimeSeconds: number;
  timestamp: string;
}

/**
 * Extended system status requirements identified for backend integration.
 * Fields not yet exposed by /health are documented as optional backend integration metrics.
 */
export interface SystemTelemetry {
  backendHealth: HealthResponse;
  modelAvailability?: {
    yoloV11?: "ready" | "loading" | "unavailable";
    byteTrack?: "ready" | "loading" | "unavailable";
  };
  databaseConnectivity?: "connected" | "disconnected" | "slow";
  resourceUtilization?: {
    gpuPercent?: number;
    cpuPercent?: number;
    memoryPercent?: number;
  };
}
