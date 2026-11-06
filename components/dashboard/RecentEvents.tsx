import type { Severity } from "@/types/events";
import MaterialIcon from "@/components/ui/MaterialIcon";

export interface EventDisplayItem {
  id: string;
  time: string;
  area: string;
  description: string;
  severity: Severity;
}

export default function RecentEvents({ events = [] }: { events?: EventDisplayItem[] }) {
  if (events.length === 0) {
    return (
      <div className="py-6 text-center text-xs text-slate-500">
        <MaterialIcon name="notifications_paused" className="h-5 w-5 text-slate-400 mx-auto mb-1.5" aria-hidden="true" />
        <p className="font-semibold text-slate-700">No active incidents</p>
        <p className="text-[11px] text-slate-400 mt-0.5">Floor operations operating within standard parameters.</p>
      </div>
    );
  }

  return (
    <ul className="space-y-2" aria-label="Recent store events stream">
      {events.map((event) => {
        const isCritical = event.severity === "critical";
        const isWarning = event.severity === "warning";

        return (
          <li
            key={event.id}
            className="flex items-start gap-3 rounded-lg border border-[#eeefec] bg-[#fafaf8] p-3 transition-colors hover:bg-white hover:border-[#e6e7e3]"
          >
            <div
              className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md ${
                isCritical
                  ? "bg-rose-100 text-rose-700"
                  : isWarning
                  ? "bg-amber-100 text-amber-800"
                  : "bg-emerald-100 text-emerald-800"
              }`}
              aria-hidden="true"
            >
              {isCritical ? (
                <MaterialIcon name="error" className="h-3.5 w-3.5" aria-hidden="true" />
              ) : isWarning ? (
                <MaterialIcon name="warning" className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <MaterialIcon name="check_circle" className="h-3.5 w-3.5" aria-hidden="true" />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-bold text-slate-900 truncate">
                  {event.area}
                </p>
                <span className="flex items-center gap-1 font-mono text-[10px] text-slate-400 shrink-0 tabular-nums">
                  <MaterialIcon name="schedule" className="h-2.5 w-2.5" aria-hidden="true" />
                  {event.time}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-slate-600 leading-snug">
                {event.description}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
