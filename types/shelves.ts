export type ShelfStatus = "ok" | "low" | "critical";

export interface ShelfItem {
  id: string;
  name: string;
  aisle: string;
  fillPct: number;
  status: ShelfStatus;
  lastChecked: string;
}

export interface ShelvesResponse {
  shelves: ShelfItem[];
  totalCount: number;
  criticalCount: number;
  lowStockCount: number;
}
