export interface TrafficPoint {
  day: string;
  customers: number;
}

export interface HourlyPoint {
  hour: string;
  customers: number;
}

export interface DwellPoint {
  section: string;
  minutes: number;
}

export interface QueuePoint {
  checkoutId: string;
  currentQueue: number;
  avgWaitMinutes: number;
  peakQueue: number;
}

export interface SectionTrafficPoint {
  section: string;
  visits: number;
  percentage: number;
}

export interface AnalyticsTrafficResponse {
  daily: TrafficPoint[];
  hourly: HourlyPoint[];
  totalCustomers: number;
}

export interface AnalyticsDwellResponse {
  bySection: DwellPoint[];
  averageDwellMinutes: number;
}

export interface AnalyticsQueuesResponse {
  queues: QueuePoint[];
  updatedAt: string;
}

export interface VisitorMetricsResponse {
  personDetections: number;
  activeTracks: number;
  uniqueDailyVisitors: number;
  visitSessions: number;
  returningVisitors: number;
  cameraTraffic: Record<string, number>;
}

export interface DailyVisitor {
  id: string;
  storeId: string;
  localDate: string;
  anonymousLabel: string;
  firstSeenAt: number;
  lastSeenAt: number;
  totalVisits: number;
  totalDwellSeconds: number;
  camerasSeen: string[];
}

export interface DailyVisitorListResponse {
  visitors: DailyVisitor[];
  totalCount: number;
  uniqueDailyVisitors: number;
  returningVisitors: number;
}
