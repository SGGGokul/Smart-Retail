/**
 * Canonical Inventory Data-Access Layer & Single Source of Truth
 *
 * Defines uniform stock thresholds and severity sorting across all pages:
 * - Overview Dashboard KPI
 * - Shelf Monitoring matrix
 * - Sidebar navigation badges
 * - RetailIQ Copilot assistant responses
 */

import type { ShelfItem, ShelfStatus } from "@/types";

export const INVENTORY_THRESHOLDS = {
  CRITICAL: 40, // < 40% is critical restock priority
  LOW: 70,      // 40% - 70% is low stock warning
  OPTIMAL: 70,  // > 70% is optimal availability
} as const;

/**
 * Derives stock status strictly from canonical thresholds.
 * - < 40%: "critical"
 * - 40% to 70%: "low"
 * - > 70%: "ok" (optimal)
 */
export function calculateShelfStatus(fillPct: number): ShelfStatus {
  if (fillPct < INVENTORY_THRESHOLDS.CRITICAL) return "critical";
  if (fillPct <= INVENTORY_THRESHOLDS.LOW) return "low";
  return "ok";
}

export interface InventorySummary {
  totalBays: number;
  criticalBays: ShelfItem[];
  lowStockBays: ShelfItem[];
  optimalBays: ShelfItem[];
  restockBays: ShelfItem[]; // Sorted strictly by severity: lowest fill first!
  criticalCount: number;
  lowStockCount: number;
  optimalCount: number;
  restockCount: number;
  overallFillPct: number;
}

/**
 * Calculates canonical inventory summary from the shelf dataset.
 * Guarantees that:
 * 1. 71% is classified as optimal ("ok"), never low or critical.
 * 2. Restock priorities are sorted by actual stock severity (lowest fill first).
 * 3. Total restock count = criticalCount + lowStockCount.
 */
export function getInventorySummary(items: ShelfItem[] = []): InventorySummary {
  const normalized: ShelfItem[] = items.map((item) => ({
    ...item,
    status: calculateShelfStatus(item.fillPct),
  }));

  // Sort by fillPct ascending: lowest fill / highest severity first!
  const criticalBays = normalized
    .filter((s) => s.status === "critical")
    .sort((a, b) => a.fillPct - b.fillPct);

  const lowStockBays = normalized
    .filter((s) => s.status === "low")
    .sort((a, b) => a.fillPct - b.fillPct);

  const optimalBays = normalized
    .filter((s) => s.status === "ok")
    .sort((a, b) => a.fillPct - b.fillPct);

  // Canonical restock list: all non-optimal bays sorted by lowest fill first
  const restockBays = [...criticalBays, ...lowStockBays].sort((a, b) => a.fillPct - b.fillPct);

  const totalFill = normalized.reduce((acc, s) => acc + s.fillPct, 0);
  const overallFillPct = normalized.length ? Math.round(totalFill / normalized.length) : 0;

  return {
    totalBays: normalized.length,
    criticalBays,
    lowStockBays,
    optimalBays,
    restockBays,
    criticalCount: criticalBays.length,
    lowStockCount: lowStockBays.length,
    optimalCount: optimalBays.length,
    restockCount: restockBays.length,
    overallFillPct,
  };
}

/**
 * Formatted string representation of current restock priority for KPI displays and Copilot responses.
 */
export function getRestockPrioritySummary(items: ShelfItem[] = []): { count: number; label: string; details: string } {
  const summary = getInventorySummary(items);
  const namesAndFills = summary.restockBays
    .map((s) => `${s.name} (${s.fillPct}%)`)
    .join(", ");

  return {
    count: summary.restockCount,
    label: summary.restockCount === 1 ? "1 zone" : `${summary.restockCount} zones`,
    details: namesAndFills || "All monitored zones at optimal capacity.",
  };
}
