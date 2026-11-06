import type { Severity, StoreEvent } from "./events";
export type { Severity, StoreEvent };

export interface AlertItem {
  id: string;
  type: string;
  time: string;
  area: string;
  severity: Severity;
  description: string;
  acknowledged: boolean;
}

export interface AlertsResponse {
  alerts: AlertItem[];
  totalCount: number;
  unacknowledgedCount: number;
}

export interface AlertUpdateRequest {
  acknowledged: boolean;
  notes?: string;
}
