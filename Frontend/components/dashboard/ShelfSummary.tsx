import Link from "next/link";
import type { ShelfItem } from "@/types/shelves";
import StatusBadge from "@/components/ui/StatusBadge";
import MaterialIcon from "@/components/ui/MaterialIcon";

export default function ShelfSummary({ items = [] }: { items?: ShelfItem[] }) {
  if (items.length === 0) {
    return (
      <div className="py-6 text-center text-xs text-slate-500">
        <MaterialIcon name="inventory" className="h-5 w-5 text-slate-400 mx-auto mb-1.5" aria-hidden="true" />
        <p className="font-semibold text-slate-700">No shelf telemetry recorded</p>
        <p className="text-[11px] text-slate-400 mt-0.5">Connect vision sensor streams to monitor shelf fill levels.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3.5">
      <ul className="divide-y divide-[#eeefec]" aria-label="Shelf status summary">
        {items.map((shelf) => {
          const isCritical = shelf.status === "critical";
          const isLow = shelf.status === "low";

          return (
            <li key={shelf.id}>
              <Link
                href="/shelf-monitoring"
                target="_self"
                className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-3 hover:bg-[#f8f8f6] rounded-md px-1.5 -mx-1.5 transition-colors group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-xs sm:text-sm font-bold text-slate-900 group-hover:text-emerald-950">{shelf.name}</p>
                    <span className="flex items-center gap-1 text-[11px] text-slate-400">
                      <MaterialIcon name="location_on" className="h-3 w-3 text-emerald-700" aria-hidden="true" />
                      {shelf.aisle}
                    </span>
                  </div>

                  {/* Precision Fill Gauge */}
                  <div className="mt-1.5 flex items-center gap-2.5">
                    <div className="h-1.5 w-28 sm:w-40 overflow-hidden rounded-full bg-[#f2f3ef]">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          isCritical
                            ? "bg-rose-600"
                            : isLow
                            ? "bg-amber-600"
                            : "bg-emerald-600"
                        }`}
                        style={{ width: `${shelf.fillPct}%` }}
                      />
                    </div>
                    <span className="font-mono text-[11px] font-semibold text-slate-700 tabular-nums">
                      {shelf.fillPct}%
                    </span>
                  </div>
                </div>

                <StatusBadge
                  variant={isCritical ? "critical" : isLow ? "warning" : "success"}
                  size="sm"
                >
                  {isCritical ? "Critical" : isLow ? "Low Stock" : "Optimal"}
                </StatusBadge>
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="pt-2.5 border-t border-[#eeefec] flex justify-end">
        <Link
          href="/shelf-monitoring"
          target="_self"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-800 hover:text-emerald-950 transition-colors group"
        >
          <span>Open Full Shelf Matrix</span>
          <MaterialIcon name="arrow_forward" className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
