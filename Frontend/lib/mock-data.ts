/**
 * Demo data for the RetailIQ dashboard.
 * All values are hardcoded placeholders for demo purposes only — they do NOT
 * represent live store analytics. Real data will be wired in Phase 3 via
 * lib/api.ts.
 */

export type ShelfStatus = "ok" | "low" | "critical";
export type Severity = "info" | "warning" | "critical";

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

export interface StoreEvent {
  id: string;
  time: string;
  area: string;
  description: string;
  severity: Severity;
}

export interface ShelfItem {
  id: string;
  name: string;
  aisle: string;
  fillPct: number;
  status: ShelfStatus;
  lastChecked: string;
}

export interface AlertItem {
  id: string;
  type: string;
  time: string;
  area: string;
  severity: Severity;
  description: string;
  acknowledged: boolean;
}

export interface VideoJob {
  id: string;
  file: string;
  uploaded: string;
  status: "queued" | "processing" | "done" | "failed";
  frames: number;
  customersDetected: number;
}

export interface ChatPrompt {
  question: string;
  answer: string;
}

export const trafficData: TrafficPoint[] = [
  { day: "Mon", customers: 942 },
  { day: "Tue", customers: 1010 },
  { day: "Wed", customers: 1158 },
  { day: "Thu", customers: 1084 },
  { day: "Fri", customers: 1372 },
  { day: "Sat", customers: 1490 },
  { day: "Sun", customers: 1248 },
];

export const hourlyData: HourlyPoint[] = [
  { hour: "07", customers: 34 },
  { hour: "08", customers: 92 },
  { hour: "09", customers: 148 },
  { hour: "10", customers: 176 },
  { hour: "11", customers: 158 },
  { hour: "12", customers: 210 },
  { hour: "13", customers: 186 },
  { hour: "14", customers: 142 },
  { hour: "15", customers: 168 },
  { hour: "16", customers: 204 },
  { hour: "17", customers: 226 },
  { hour: "18", customers: 214 },
  { hour: "19", customers: 176 },
  { hour: "20", customers: 118 },
  { hour: "21", customers: 62 },
];

export const dwellData: DwellPoint[] = [
  { section: "Produce", minutes: 6 },
  { section: "Bakery", minutes: 4 },
  { section: "Dairy", minutes: 3 },
  { section: "Beverages", minutes: 5 },
  { section: "Checkout", minutes: 7 },
];

export const recentEvents: StoreEvent[] = [
  { id: "ev-01", time: "14:32", area: "Checkout 3", description: "Queue exceeded 4 people for over 5 minutes.", severity: "warning" },
  { id: "ev-02", time: "14:05", area: "Aisle 4", description: "Beverages shelf fill dropped below 40%.", severity: "critical" },
  { id: "ev-03", time: "13:47", area: "Entrance", description: "Customer count for the hour is running 8% above average.", severity: "info" },
  { id: "ev-04", time: "12:58", area: "Aisle 2", description: "Dairy shelf restock completed.", severity: "info" },
  { id: "ev-05", time: "11:26", area: "Video pipeline", description: "Morning ingestion job finished successfully.", severity: "info" },
  { id: "ev-06", time: "10:12", area: "Aisle 7", description: "Bakery display stock critically low.", severity: "critical" },
];

export const shelves: ShelfItem[] = [
  { id: "sh-A7", name: "Bakery", aisle: "Aisle 7", fillPct: 26, status: "critical", lastChecked: "10:12" },
  { id: "sh-A4", name: "Beverages", aisle: "Aisle 4", fillPct: 38, status: "critical", lastChecked: "14:05" },
  { id: "sh-A2", name: "Dairy", aisle: "Aisle 2", fillPct: 58, status: "low", lastChecked: "12:58" },
  { id: "sh-A1", name: "Produce", aisle: "Aisle 1", fillPct: 71, status: "ok", lastChecked: "13:20" },
  { id: "sh-A5", name: "Snacks", aisle: "Aisle 5", fillPct: 84, status: "ok", lastChecked: "13:44" },
  { id: "sh-A6", name: "Household", aisle: "Aisle 6", fillPct: 92, status: "ok", lastChecked: "13:44" },
];

export const lowStockCount = 1;
export const criticalCount = 2;
export const restockCount = 3;

export const alerts: AlertItem[] = [
  { id: "al-01", type: "Shelf low stock", time: "14:05", area: "Aisle 4", severity: "critical", description: "Beverages shelf fill dropped below 40%.", acknowledged: false },
  { id: "al-02", type: "Shelf low stock", time: "10:12", area: "Aisle 7", severity: "critical", description: "Bakery display stock critically low.", acknowledged: false },
  { id: "al-03", type: "Queue alert", time: "14:32", area: "Checkout 3", severity: "warning", description: "Queue exceeded 4 people for over 5 minutes.", acknowledged: false },
  { id: "al-04", type: "Queue alert", time: "17:21", area: "Checkout 1", severity: "warning", description: "Wait time estimated above 6 minutes.", acknowledged: true },
  { id: "al-05", type: "Traffic anomaly", time: "13:47", area: "Entrance", severity: "info" as const, description: "Customer count running 8% above the hourly average.", acknowledged: true },
  { id: "al-06", type: "System", time: "08:14", area: "Camera 2", severity: "info", description: "Camera reconnected after short offline period.", acknowledged: true },
  { id: "al-07", type: "Shelf low stock", time: "12:58", area: "Aisle 2", severity: "warning", description: "Dairy shelf fill below 60%. Restock completed.", acknowledged: true },
  { id: "al-08", type: "System", time: "07:02", area: "Pipeline", description: "Daily ingestion job started.", severity: "info" as const, acknowledged: true },
];

export const videoJobs: VideoJob[] = [
  { id: "vj-01", file: "store_morning_cam1.mp4", uploaded: "Today 07:03", status: "done", frames: 5400, customersDetected: 342 },
  { id: "vj-02", file: "store_afternoon_cam2.mp4", uploaded: "Today 12:10", status: "done", frames: 4800, customersDetected: 418 },
  { id: "vj-03", file: "cam3_evening.mp4", uploaded: "Today 14:22", status: "processing", frames: 0, customersDetected: 0 },
  { id: "vj-04", file: "weekend_promo_cam1.mp4", uploaded: "Yesterday 09:40", status: "done", frames: 6100, customersDetected: 512 },
];

export const chatPrompts: ChatPrompt[] = [
  {
    question: "How many customers visited today?",
    answer: "In-store camera telemetry recorded 1,248 customers today, up 6.2% compared to yesterday's benchmark.",
  },
  {
    question: "Which shelves need restocking?",
    answer: "Aisle restocking audit: exactly 3 zones currently require replenishment, sorted by severity:\n1. Bakery (Aisle 7): 26% fill — Critical\n2. Beverages (Aisle 4): 38% fill — Critical\n3. Dairy (Aisle 2): 58% fill — Low stock\nProduce (71%), Snacks (84%), and Household (92%) remain at optimal availability (>70%).",
  },
  {
    question: "What are the busiest hours today?",
    answer: "Footfall traffic peaks between 17:00 and 18:00 (226 customers) with a secondary lunchtime surge between 12:00 and 13:00 (210 customers).",
  },
  {
    question: "Summarize today's alerts.",
    answer: "There are currently 3 active unacknowledged incidents: 2 critical shelf-stock alerts on Aisles 7 & 4, and 1 queue bottleneck alert at Checkout Lane 3.",
  },
];

export const suggestedQuestions = chatPrompts.map((p) => p.question);

export interface QueueDataPoint {
  checkoutId: string;
  name: string;
  currentQueue: number;
  avgWaitMinutes: number;
  peakQueue: number;
  status: "normal" | "busy" | "congested";
}

export const queueData: QueueDataPoint[] = [
  { checkoutId: "co-1", name: "Checkout 1 (Express)", currentQueue: 2, avgWaitMinutes: 2.5, peakQueue: 4, status: "normal" },
  { checkoutId: "co-2", name: "Checkout 2 (Standard)", currentQueue: 3, avgWaitMinutes: 4.2, peakQueue: 5, status: "busy" },
  { checkoutId: "co-3", name: "Checkout 3 (Standard)", currentQueue: 4, avgWaitMinutes: 6.8, peakQueue: 7, status: "congested" },
  { checkoutId: "co-4", name: "Checkout 4 (Self-Serve)", currentQueue: 1, avgWaitMinutes: 1.2, peakQueue: 3, status: "normal" },
];

export interface SectionTrafficItem {
  section: string;
  visits: number;
  percentage: number;
  trend: "up" | "down" | "flat";
}

export const sectionTrafficData: SectionTrafficItem[] = [
  { section: "Produce", visits: 864, percentage: 32, trend: "up" },
  { section: "Dairy & Eggs", visits: 680, percentage: 25, trend: "up" },
  { section: "Beverages", visits: 520, percentage: 19, trend: "down" },
  { section: "Bakery", visits: 410, percentage: 15, trend: "flat" },
  { section: "Household & Snacks", visits: 246, percentage: 9, trend: "up" },
];

