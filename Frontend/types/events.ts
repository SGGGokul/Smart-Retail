export type Severity = "info" | "warning" | "critical";

export interface StoreEvent {
  id: string;
  time: string;
  area: string;
  description: string;
  severity: Severity;
}

export type ConfirmationStatus = "candidate" | "confirmed" | "rejected" | "uncertain";

export interface RetailEvent {
  id: string;
  storeId: string;
  cameraId: string;
  eventType: string;
  timestamp: number;
  confidence: number;
  confirmationStatus: ConfirmationStatus;
  visitorId?: string | null;
  sessionId?: string | null;
  shelfId?: string | null;
  zoneId?: string | null;
  productId?: string | null;
  productClass?: string | null;
  evidence?: Record<string, any>;
  relatedEventId?: string | null;
}

export interface EventTimelineResponse {
  events: RetailEvent[];
  totalCount: number;
  candidateCount: number;
  confirmedCount: number;
}
