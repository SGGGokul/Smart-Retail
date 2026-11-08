export type Severity = "info" | "warning" | "critical";

export interface StoreEvent {
  id: string;
  time: string;
  area: string;
  description: string;
  severity: Severity;
}
