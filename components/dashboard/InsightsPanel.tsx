import Link from "next/link";
import MaterialIcon from "@/components/ui/MaterialIcon";
import type { AnalyticsSummaryResponse } from "@/types/dashboard";

interface InsightsPanelProps {
  summary?: AnalyticsSummaryResponse | null;
  isLoading?: boolean;
}

export default function InsightsPanel({ summary, isLoading = false }: InsightsPanelProps) {
  if (isLoading) {
    return (
      <section
        aria-label="Loading operational insights"
        className="rounded-xl border border-[#e6e7e3] bg-white p-5 animate-pulse"
      >
        <div className="h-4 w-48 bg-slate-200 rounded mb-4" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          <div className="h-28 bg-slate-100 rounded-lg" />
          <div className="h-28 bg-slate-100 rounded-lg" />
          <div className="h-28 bg-slate-100 rounded-lg" />
        </div>
      </section>
    );
  }

  // Derive genuine operational insights from real summary metrics
  const insights = [];

  if (summary) {
    if (summary.todayCustomers > 0) {
      insights.push({
        id: "in-traffic",
        category: "traffic" as const,
        title: "Customer Ingress Volume",
        stat: `${summary.todayCustomers.toLocaleString()} visitors (${summary.todayCustomersDelta || "recorded today"})`,
        body: "Calculated from store entrance video feeds. Use footfall curves to optimize staff scheduling.",
        href: "/customer-analytics",
        actionText: "View traffic curve",
      });
    }

    if (summary.shelvesNeedingRestock > 0 || summary.criticalShelvesCount > 0) {
      insights.push({
        id: "in-inventory",
        category: "inventory" as const,
        title: "Shelf Stock Depletion",
        stat: `${summary.criticalShelvesCount} critical · ${summary.lowStockShelvesCount} low stock zones`,
        body: "Computer-vision fill estimation identified shelf bays below restock threshold.",
        href: "/shelf-monitoring",
        actionText: "Open shelf matrix",
      });
    }

    if (summary.longestQueueCheckout && summary.longestQueueCheckout !== "—") {
      insights.push({
        id: "in-queue",
        category: "queue" as const,
        title: "Checkout Flow Status",
        stat: `${summary.longestQueueCheckout} (${summary.longestQueueCount} shoppers waiting)`,
        body: "Queue monitoring detects wait times and recommends register allocation adjustments.",
        href: "/alerts",
        actionText: "Review queue events",
      });
    }
  }

  return (
    <section
      aria-label="Actionable store insights"
      className="rounded-xl border border-[#e6e7e3] bg-white p-5"
    >
      <div className="flex items-center justify-between pb-3.5 border-b border-[#eeefec]">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-900 text-emerald-200">
            <MaterialIcon name="analytics" className="h-3.5 w-3.5" aria-hidden="true" />
          </span>
          <h2 className="font-heading text-sm font-bold text-slate-900 tracking-normal">
            Operational Telemetry Insights
          </h2>
        </div>
        <span className="text-[11px] font-mono text-slate-400">
          {summary ? "Synthesized from CV Telemetry" : "Awaiting Backend Data"}
        </span>
      </div>

      {insights.length === 0 ? (
        <div className="mt-3.5 rounded-lg border border-dashed border-[#e6e7e3] bg-[#fafaf8] p-5 text-center text-xs text-slate-500">
          <MaterialIcon name="info" className="h-4 w-4 text-slate-400 mx-auto mb-1" aria-hidden="true" />
          <p className="font-semibold text-slate-700">No active operational alerts or anomalies detected</p>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Real-time insights appear when computer-vision sensors report footfall surges, stock depletion, or queue bottlenecks.
          </p>
        </div>
      ) : (
        <div className="mt-3.5 grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {insights.map((insight) => (
            <div
              key={insight.id}
              className="flex flex-col justify-between rounded-lg border border-[#eeefec] bg-[#fafaf8] p-3.5 transition-colors hover:bg-white hover:border-[#e6e7e3]"
            >
              <div>
                <div className="flex items-center gap-1.5 text-[11px] font-bold">
                  {insight.category === "traffic" && (
                    <span className="text-emerald-800 flex items-center gap-1">
                      <MaterialIcon name="groups" className="h-3.5 w-3.5" aria-hidden="true" />
                      Footfall Pattern
                    </span>
                  )}
                  {insight.category === "inventory" && (
                    <span className="text-rose-800 flex items-center gap-1">
                      <MaterialIcon name="warning" className="h-3.5 w-3.5" aria-hidden="true" />
                      Inventory Warning
                    </span>
                  )}
                  {insight.category === "queue" && (
                    <span className="text-amber-800 flex items-center gap-1">
                      <MaterialIcon name="schedule" className="h-3.5 w-3.5" aria-hidden="true" />
                      Bottleneck Detect
                    </span>
                  )}
                </div>

                <h3 className="mt-1.5 text-xs font-bold text-slate-900">
                  {insight.title}
                </h3>
                <div className="mt-1.5 rounded bg-white border border-[#eeefec] px-2 py-1 text-[11px] font-semibold text-slate-900 tabular-nums">
                  {insight.stat}
                </div>
                <p className="mt-1.5 text-xs text-slate-600 leading-normal">
                  {insight.body}
                </p>
              </div>

              {insight.href && (
                <div className="mt-3 pt-2.5 border-t border-[#eeefec]/80 flex justify-end">
                  <Link
                    href={insight.href}
                    className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-800 hover:text-emerald-950 transition-colors group"
                  >
                    <span>{insight.actionText || "Investigate"}</span>
                    <MaterialIcon name="arrow_forward" className="h-3 w-3 group-hover:translate-x-0.5 transition-transform" aria-hidden="true" />
                  </Link>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
