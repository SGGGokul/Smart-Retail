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
