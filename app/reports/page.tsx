"use client";

import { useState, useEffect, useCallback } from "react";
import PageHeader from "@/components/dashboard/PageHeader";
import ChartCard from "@/components/ui/ChartCard";
import StatusBadge from "@/components/ui/StatusBadge";
import NoticeBanner from "@/components/ui/NoticeBanner";
import EmptyState from "@/components/ui/EmptyState";
import MaterialIcon from "@/components/ui/MaterialIcon";
import { CardSkeleton, ChartSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import TrafficLineChart from "@/components/charts/TrafficLineChart";
import HourlyBarChart from "@/components/charts/HourlyBarChart";
import { getReportBundle, type ReportBundle } from "@/lib/api/reports";

type DateRange = "today" | "7d" | "30d";

export default function ReportsPage() {
  const [selectedRange, setSelectedRange] = useState<DateRange>("7d");
  const [bundle, setBundle] = useState<ReportBundle | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const fetchBundle = useCallback(async (range: DateRange, signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getReportBundle(range, signal);
      if (signal?.aborted) return;
      setBundle(data);
    } catch (err) {
      if (signal?.aborted) return;
      setError(
        `Failed to gather report telemetry: ${(err as Error).message}. Verify FastAPI backend connectivity.`
      );
      setBundle(null);
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchBundle(selectedRange, controller.signal);

    return () => {
      controller.abort();
    };
  }, [selectedRange, fetchBundle]);

  const handleExportCSV = () => {
    if (!bundle) return;
    setIsExporting(true);

    try {
      const footfallVal = bundle.traffic.totalCustomers ?? bundle.summary.todayCustomers ?? 0;
      const dwellVal = bundle.dwell.averageDwellMinutes ?? bundle.summary.avgDwellMinutes ?? 0;
      const incidentVal = bundle.alerts.totalCount ?? 0;
      const restockVal = bundle.summary.shelvesNeedingRestock ?? 0;

      const rows: string[][] = [
        ["RetailIQ Store Performance Report", `Generated: ${new Date().toISOString()}`],
        ["Date Range", selectedRange.toUpperCase()],
        ["Data Source", "FastAPI Computer-Vision Backend Service"],
        [],
        ["SUMMARY METRICS"],
        ["Metric", "Value", "Context"],
        ["Total Footfall", String(footfallVal), bundle.summary.todayCustomersDelta || ""],
        ["Average Dwell Time", `${dwellVal} min`, bundle.summary.avgDwellDelta || ""],
        ["Logged Incidents", `${incidentVal} alerts`, `${bundle.alerts.unacknowledgedCount ?? 0} unacknowledged`],
        ["Restock Depletions", `${restockVal} zones`, `${bundle.summary.criticalShelvesCount ?? 0} critical`],
        [],
        ["DAILY TRAFFIC DATA"],
        ["Day", "Customers"],
        ...(bundle.traffic.daily || []).map((t) => [t.day, String(t.customers)]),
        [],
        ["HOURLY TRAFFIC DATA"],
        ["Hour", "Customers"],
        ...(bundle.traffic.hourly || []).map((h) => [`${h.hour}:00`, String(h.customers)]),
        [],
        ["DEPARTMENT DWELL TIME"],
        ["Department", "Average Dwell (Minutes)"],
        ...(bundle.dwell.bySection || []).map((d) => [d.section, String(d.minutes)]),
      ];

      const csvContent =
        "data:text/csv;charset=utf-8," +
        rows.map((row) => row.map((val) => `"${val.replace(/"/g, '""')}"`).join(",")).join("\n");

      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      const filename = `retailiq_report_${selectedRange}_${new Date().toISOString().slice(0, 10)}.csv`;
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setExportNotice(`Exported ${filename} successfully in RFC 4180 format.`);
      setTimeout(() => setExportNotice(null), 4000);
    } finally {
      setIsExporting(false);
    }
  };

  const totalFootfall = bundle?.traffic?.totalCustomers ?? bundle?.summary?.todayCustomers ?? null;
  const avgDwell = bundle?.dwell?.averageDwellMinutes ?? bundle?.summary?.avgDwellMinutes ?? null;
  const loggedIncidents = bundle?.alerts?.totalCount ?? null;
  const stockoutZones = bundle?.summary?.shelvesNeedingRestock ?? null;

  return (
    <div className="space-y-5">
      {/* Header */}
      <PageHeader
        title="Reports &amp; Historical Exports"
        description="Aggregate store telemetry reporting, departmental benchmark evaluations, and structured RFC 4180 CSV exports."
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleExportCSV}
              disabled={isExporting || isLoading || !bundle}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-900 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-950 disabled:opacity-50 transition-colors shadow-2xs cursor-pointer"
            >
              {isExporting ? (
                <>
                  <MaterialIcon name="table_chart" className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  <span>Generating CSV...</span>
                </>
              ) : (
                <>
                  <MaterialIcon name="download" className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Export CSV Report</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => fetchBundle(selectedRange)}
              disabled={isLoading}
              className="flex items-center gap-1 rounded-lg border border-[#e6e7e3] bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-[#f8f8f6] disabled:opacity-50 transition-colors shadow-2xs cursor-pointer"
            >
              <MaterialIcon
                name="refresh"
                className={`h-3.5 w-3.5 text-emerald-800 ${isLoading ? "animate-spin" : ""}`}
                aria-hidden="true"
              />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>
        }
      />

      {error && (
        <NoticeBanner
          type="critical"
          message={
            <div className="flex flex-wrap items-center justify-between gap-2 w-full">
              <span>{error}</span>
              <button
                type="button"
                onClick={() => fetchBundle(selectedRange)}
                className="rounded bg-rose-200/60 px-2 py-0.5 font-bold hover:bg-rose-200 text-rose-950 transition-colors"
              >
                Retry
              </button>
            </div>
          }
          onDismiss={() => setError(null)}
        />
      )}

      {exportNotice && (
        <NoticeBanner
          type="success"
          message={exportNotice}
          onDismiss={() => setExportNotice(null)}
        />
      )}

      {/* Scope Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-xl border border-[#e6e7e3] bg-white p-3.5">
        <div className="flex items-center gap-2">
          <MaterialIcon name="calendar_today" className="h-4 w-4 text-emerald-800" aria-hidden="true" />
          <span className="text-xs font-semibold text-slate-800">Reporting Interval:</span>
          <span className="text-xs text-slate-500">
            {selectedRange === "today" ? "Today" : selectedRange === "7d" ? "Past 7 Days" : "Past 30 Days"}
          </span>
        </div>

        <div
          className="flex items-center p-0.5 rounded-lg bg-[#f2f3ef] border border-[#e6e7e3]"
          role="group"
          aria-label="Select report interval"
        >
          {(
            [
              { id: "today", label: "Today" },
              { id: "7d", label: "7 Days" },
              { id: "30d", label: "30 Days" },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelectedRange(item.id)}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer ${
                selectedRange === item.id
                  ? "bg-white text-slate-900 shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Summary Row */}
      {isLoading ? (
        <section aria-label="Loading report metrics" className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </section>
      ) : (
        <section aria-label="Report metrics summary" className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <span className="text-xs text-slate-500 font-medium block">Total Footfall</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-slate-900 tabular-nums block">
              {totalFootfall != null ? totalFootfall.toLocaleString() : "—"}
            </span>
            <span className="text-[11px] font-semibold text-emerald-800 mt-0.5 block tabular-nums">
              {bundle?.summary?.todayCustomersDelta || "Period aggregate"}
            </span>
          </div>

          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <span className="text-xs text-slate-500 font-medium block">Avg Store Dwell</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-slate-900 tabular-nums block">
              {avgDwell != null ? `${avgDwell} min` : "—"}
            </span>
            <span className="text-[11px] text-slate-500 mt-0.5 block">
              {bundle?.summary?.avgDwellDelta || "Departmental baseline"}
            </span>
          </div>

          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <span className="text-xs text-slate-500 font-medium block">Logged Incidents</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-slate-900 tabular-nums block">
              {loggedIncidents != null ? `${loggedIncidents} alerts` : "—"}
            </span>
            <span className="text-[11px] text-amber-800 mt-0.5 block">
              {bundle?.alerts ? `${bundle.alerts.unacknowledgedCount} unacknowledged` : "—"}
            </span>
          </div>

          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <span className="text-xs text-slate-500 font-medium block">Stockout Zones</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-slate-900 tabular-nums block">
              {stockoutZones != null ? `${stockoutZones} zones` : "—"}
            </span>
            <span className="text-[11px] text-slate-500 mt-0.5 block">
              {bundle?.summary ? `${bundle.summary.criticalShelvesCount} critical alerts` : "—"}
            </span>
          </div>
        </section>
      )}

      {/* Charts Grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title={`Footfall Trajectory (${selectedRange.toUpperCase()})`}
          description="Customer detection volume across the selected interval"
        >
          {isLoading ? (
            <ChartSkeleton />
          ) : !bundle?.traffic?.daily || bundle.traffic.daily.length === 0 ? (
            <EmptyState
              icon="trending_up"
              title="No trajectory records"
              description="No daily traffic telemetry available for this range."
            />
          ) : (
            <TrafficLineChart data={bundle.traffic.daily} />
          )}
        </ChartCard>

        <ChartCard
          title="Operating Hour Density Profile"
          description="Detection distribution across standard operating hours"
        >
          {isLoading ? (
            <ChartSkeleton />
          ) : !bundle?.traffic?.hourly || bundle.traffic.hourly.length === 0 ? (
            <EmptyState
              icon="schedule"
              title="No hourly density data"
              description="Hourly ingress data has not been logged."
            />
          ) : (
            <HourlyBarChart data={bundle.traffic.hourly} />
          )}
        </ChartCard>
      </div>

      {/* Telemetry Preview Table */}
      <section
        aria-label="CSV data preview"
        className="rounded-xl border border-[#e6e7e3] bg-white p-4.5 space-y-3"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 pb-2.5 border-b border-[#eeefec]">
          <div>
            <h2 className="font-heading text-sm font-bold text-slate-900">
              Department Telemetry Summary Preview
            </h2>
            <p className="text-xs text-slate-500">
              Departmental dwell times included in RFC 4180 spreadsheet export
            </p>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Format: CSV (UTF-8)
          </span>
        </div>

        {isLoading ? (
          <TableSkeleton rows={4} />
        ) : !bundle?.dwell?.bySection || bundle.dwell.bySection.length === 0 ? (
          <EmptyState
            icon="table_chart"
            title="No section dwell data"
            description="Department dwell records will populate when backend data is received."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" aria-label="Summary telemetry preview table">
              <thead className="border-b border-[#eeefec] bg-[#f8f8f6] text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="px-3.5 py-2">Department</th>
                  <th className="px-3.5 py-2">Avg Dwell</th>
                  <th className="px-3.5 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eeefec]">
                {bundle.dwell.bySection.map((d) => (
                  <tr key={d.section} className="hover:bg-[#fafaf8] transition-colors">
                    <td className="px-3.5 py-2.5 font-bold text-slate-900">
                      {d.section}
                    </td>
                    <td className="px-3.5 py-2.5 font-mono font-bold text-slate-800 tabular-nums">
                      {d.minutes} min
                    </td>
                    <td className="px-3.5 py-2.5">
                      <StatusBadge variant="success" size="sm">
                        Monitored
                      </StatusBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
