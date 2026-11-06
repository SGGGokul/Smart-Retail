import Link from "next/link";
import MaterialIcon from "@/components/ui/MaterialIcon";
import type { AnalyticsSummaryResponse } from "@/types/dashboard";
import { CardSkeleton } from "@/components/ui/Skeleton";

interface OperationalMetricsProps {
  summary: AnalyticsSummaryResponse | null;
  timeframe: "today" | "7d" | "30d";
  isLoading?: boolean;
}

export default function OperationalMetrics({
  summary,
  timeframe,
  isLoading = false,
}: OperationalMetricsProps) {
  const isToday = timeframe === "today";

  if (isLoading) {
    return (
      <section aria-label="Loading operational metrics" className="grid grid-cols-1 md:grid-cols-12 gap-3.5">
        <div className="md:col-span-4"><CardSkeleton /></div>
        <div className="md:col-span-3"><CardSkeleton /></div>
        <div className="md:col-span-3"><CardSkeleton /></div>
        <div className="md:col-span-2"><CardSkeleton /></div>
      </section>
    );
  }

  const customers = summary?.todayCustomers != null ? summary.todayCustomers.toLocaleString() : "—";
  const customerDelta = summary?.todayCustomersDelta || (summary ? "Current telemetry" : "Unavailable");
  const dwell = summary?.avgDwellMinutes != null ? `${summary.avgDwellMinutes} min` : "—";
  const dwellDelta = summary?.avgDwellDelta || (summary ? "Measured baseline" : "Unavailable");
  const longestQueue = summary?.longestQueueCheckout || "—";
  const queueDelta = summary?.longestQueueCount != null ? `${summary.longestQueueCount} waiting` : "No queue data";
  const restock = summary?.shelvesNeedingRestock != null ? `${summary.shelvesNeedingRestock} zones` : "—";
  const restockDelta = summary
    ? `${summary.criticalShelvesCount ?? 0} critical · ${summary.lowStockShelvesCount ?? 0} low stock`
    : "No shelf data";

  return (
    <section aria-label="Primary operational metrics" className="grid grid-cols-1 md:grid-cols-12 gap-3.5">
      {/* 1. Footfall — Dominant Operational Anchor (Col 1-4) */}
      <div className="md:col-span-4 rounded-xl border border-[#e6e7e3] bg-white p-4.5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Customer Footfall</span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border bg-emerald-50 text-emerald-800 border-emerald-200/80">
              {summary ? "Live Telemetry" : "Backend Offline"}
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-2.5">
            <span className="font-heading text-3xl font-extrabold tracking-tight text-slate-900 tabular-nums">
              {customers}
            </span>
            {customerDelta !== "Unavailable" && (
              <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-emerald-700 tabular-nums">
                <MaterialIcon name="north_east" className="h-3 w-3" aria-hidden="true" />
                {customerDelta}
              </span>
            )}
          </div>

          <p className="mt-1 text-xs text-slate-500 leading-normal">
            {summary
              ? isToday
                ? "Aggregated from vision ingress points for today."
                : `Storewide visitor detections for the ${timeframe} period.`
              : "Awaiting data from FastAPI backend."}
          </p>
        </div>

        <div className="mt-4 pt-3 border-t border-[#eeefec] flex items-center justify-between text-xs text-slate-700 font-medium">
          <span>Source: Vision Telemetry</span>
          <span className="text-slate-500">{summary ? "Synced" : "Not connected"}</span>
        </div>
      </div>

      {/* 2. Average Dwell Time (Col 5-7) */}
      <div className="md:col-span-3 rounded-xl border border-[#e6e7e3] bg-white p-4.5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Avg Dwell Time</span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border bg-slate-100 text-slate-700 border-slate-200">
              {dwell !== "—" ? "Measured" : "Pending"}
            </span>
          </div>

          <div className="mt-3">
            <span className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 tabular-nums">
              {dwell}
            </span>
            <p className="mt-1 text-xs font-medium text-slate-600">
              {dwellDelta}
            </p>
            <p className="mt-0.5 text-[11px] text-slate-500">
              Storewide customer dwell duration
            </p>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-[#eeefec] text-xs">
          <div className="flex justify-between items-center">
            <span className="font-medium text-slate-600">Metric Status:</span>
            <span className="font-semibold text-slate-800">{dwell !== "—" ? "Active" : "Awaiting data"}</span>
          </div>
        </div>
      </div>

      {/* 3. Longest Queue / Checkout Bottleneck (Col 8-10) */}
      <div className="md:col-span-3 rounded-xl border border-[#e6e7e3] bg-white p-4.5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Queue Peak</span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border bg-amber-50 text-amber-800 border-amber-200/80">
              {longestQueue !== "—" ? "Monitored" : "Pending"}
            </span>
          </div>

          <div className="mt-3">
            <span className="font-heading text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
              {longestQueue}
            </span>
            <p className="mt-1 text-xs font-semibold text-amber-800 tabular-nums">
              {queueDelta}
            </p>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-[#eeefec] flex items-center justify-between text-xs">
          <span className="font-medium text-slate-700">Checkout Bottleneck</span>
          <span className="font-medium text-slate-600">{longestQueue !== "—" ? "Active" : "No queue"}</span>
        </div>
      </div>

      {/* 4. Restock Alerts / Shelf Health (Col 11-12) */}
      <div className="md:col-span-2 rounded-xl border border-rose-200/80 bg-rose-50/40 p-4.5 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs font-medium text-rose-800">
            <span>Restock Priority</span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border bg-rose-100 text-rose-800 border-rose-300">
              {summary?.criticalShelvesCount ? `${summary.criticalShelvesCount} Urgent` : "Shelves"}
            </span>
          </div>

          <div className="mt-3">
            <span className="font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-rose-950 tabular-nums">
              {restock}
            </span>
            <p className="mt-1 text-xs font-semibold text-rose-800 truncate" title={restockDelta}>
              {restockDelta}
            </p>
          </div>
        </div>

        <div className="mt-4 pt-2">
          <Link
            href="/shelf-monitoring"
            className="inline-flex items-center gap-1 text-xs font-bold text-rose-900 hover:text-rose-950 group"
          >
            <span>Resolve in Matrix</span>
            <MaterialIcon name="arrow_forward" className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </section>
  );
}
