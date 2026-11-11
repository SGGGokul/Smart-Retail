export interface AnalyticsSummaryResponse {
  todayCustomers: number;
  todayCustomersDelta: string;
  avgDwellMinutes: number;
  avgDwellDelta: string;
  longestQueueCheckout: string;
  longestQueueCount: number;
  shelvesNeedingRestock: number;
  criticalShelvesCount: number;
  lowStockShelvesCount: number;
}

export interface OperationalInsight {
  id: string;
  category: "traffic" | "inventory" | "queue";
  title: string;
  stat: string;
  body: string;
  href?: string;
  actionText?: string;
}
