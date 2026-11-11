import type { ReactNode } from "react";
import MaterialIcon from "@/components/ui/MaterialIcon";

interface KpiCardProps {
  label: string;
  value: string;
  delta?: string;
  trend?: "up" | "down" | "flat";
  icon?: ReactNode;
  subtitle?: string;
  variant?: "default" | "critical" | "warning" | "highlight";
}

export default function KpiCard({
  label,
  value,
  delta,
  trend,
  icon,
  subtitle,
  variant = "default",
}: KpiCardProps) {
  const isCritical = variant === "critical";
  const isWarning = variant === "warning";
  const isHighlight = variant === "highlight";

  return (
    <div
      className={`flex flex-col justify-between rounded-xl border p-4.5 transition-colors ${
        isCritical
          ? "border-rose-200 bg-rose-50/40"
          : isWarning
          ? "border-amber-200 bg-amber-50/40"
          : isHighlight
          ? "border-emerald-200 bg-emerald-50/30"
          : "border-[#e6e7e3] bg-white hover:border-slate-300"
      }`}
    >
      <div>
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold text-slate-500">{label}</p>
          {icon ? (
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-lg text-slate-600 ${
                isCritical
                  ? "text-rose-700 bg-rose-100"
                  : isWarning
                  ? "text-amber-700 bg-amber-100"
                  : "text-emerald-700 bg-[#f2f3ef]"
              }`}
              aria-hidden="true"
            >
              {icon}
            </span>
          ) : null}
        </div>

        <p className="mt-2.5 font-heading text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 tabular-nums">
          {value}
        </p>
      </div>

      <div className="mt-3.5 flex items-center justify-between border-t border-[#eeefec] pt-2.5 text-[11px]">
        {delta ? (
          <div className="flex items-center gap-1 font-medium tabular-nums">
            {trend === "up" && (
              <span className="inline-flex items-center gap-0.5 font-semibold text-emerald-800">
                <MaterialIcon name="north_east" className="h-3 w-3" aria-hidden="true" />
                <span>{delta}</span>
              </span>
            )}
            {trend === "down" && (
              <span className="inline-flex items-center gap-0.5 font-semibold text-rose-800">
                <MaterialIcon name="south_east" className="h-3 w-3" aria-hidden="true" />
                <span>{delta}</span>
              </span>
            )}
            {trend === "flat" && (
              <span className="inline-flex items-center gap-0.5 font-medium text-slate-600">
                <MaterialIcon name="remove" className="h-3 w-3" aria-hidden="true" />
                <span>{delta}</span>
              </span>
            )}
            {!trend && <span className="text-slate-600">{delta}</span>}
          </div>
        ) : subtitle ? (
          <span className="text-slate-500">{subtitle}</span>
        ) : (
          <span className="text-slate-400">Simulated telemetry</span>
        )}

        <span className="rounded bg-[#f8f8f6] px-1.5 py-0.2 text-[9px] font-bold text-slate-400 border border-[#e6e7e3]">
          Demo
        </span>
      </div>
    </div>
  );
}
