export type ShelfStatus = "ok" | "low" | "critical";

export interface ShelfItem {
  id: string;
  name: string;
  aisle: string;
  fillPct: number;
  status: ShelfStatus;
  lastChecked: string;
  capacity?: number;
  occupancy?: number;
  emptyPositions?: number;
  tierCount?: number;
  productClasses?: string[];
}

export interface ShelvesResponse {
  shelves: ShelfItem[];
  totalCount: number;
  criticalCount: number;
  lowStockCount: number;
}

export interface ShelfMetricsResponse {
  shelfOccupancyPercentage: number;
  emptyPositions: number;
  lowStockCount: number;
  outOfStockCount: number;
  pickupCandidates: number;
  confirmedPickups: number;
  returnCandidates: number;
  confirmedReturns: number;
  customerShelfInteractions: number;
}
