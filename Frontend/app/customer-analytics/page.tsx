"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import PageHeader from "@/components/dashboard/PageHeader";
import TrafficLineChart from "@/components/charts/TrafficLineChart";
import HourlyBarChart from "@/components/charts/HourlyBarChart";
import ChartCard from "@/components/ui/ChartCard";
import StatusBadge from "@/components/ui/StatusBadge";
import MaterialIcon from "@/components/ui/MaterialIcon";
import EmptyState from "@/components/ui/EmptyState";
import NoticeBanner from "@/components/ui/NoticeBanner";
import { CardSkeleton, ChartSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import {
  getCustomerTraffic,
  getCustomerDwellTime,
  getCheckoutQueues,
} from "@/lib/api/customer-analytics";
import { getDashboardSummary } from "@/lib/api/dashboard";
import type {
  AnalyticsTrafficResponse,
  AnalyticsDwellResponse,
  AnalyticsQueuesResponse,
  QueuePoint,
} from "@/types/analytics";
import type { AnalyticsSummaryResponse } from "@/types/dashboard";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

type TimeRange = "today" | "7d" | "30d";

export default function CustomerAnalyticsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [traffic, setTraffic] = useState<AnalyticsTrafficResponse | null>(null);
  const [dwell, setDwell] = useState<AnalyticsDwellResponse | null>(null);
  const [queues, setQueues] = useState<AnalyticsQueuesResponse | null>(null);
  const [summary, setSummary] = useState<AnalyticsSummaryResponse | null>(null);

  const loadData = useCallback(async (range: TimeRange, signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);

    try {
      const [trafficRes, dwellRes, queuesRes, summaryRes] = await Promise.allSettled([
        getCustomerTraffic(range, signal),
        getCustomerDwellTime(signal),
        getCheckoutQueues(signal),
        getDashboardSummary(signal),
      ]);

      if (signal?.aborted) return;

      let failures = 0;
      let lastErrMsg = "";

      if (trafficRes.status === "fulfilled") {
        setTraffic(trafficRes.value);
      } else {
        failures++;
        lastErrMsg = trafficRes.reason?.message || "Failed to load traffic";
      }

      if (dwellRes.status === "fulfilled") {
        setDwell(dwellRes.value);
      } else {
        failures++;
        lastErrMsg = dwellRes.reason?.message || "Failed to load dwell time";
      }

      if (queuesRes.status === "fulfilled") {
        setQueues(queuesRes.value);
      } else {
        failures++;
        lastErrMsg = queuesRes.reason?.message || "Failed to load queues";
      }

      if (summaryRes.status === "fulfilled") {
        setSummary(summaryRes.value);
      } else {
        failures++;
        lastErrMsg = summaryRes.reason?.message || "Failed to load summary";
      }

      if (failures === 4) {
        setError(
          `Unable to connect to FastAPI customer analytics endpoints. Verify backend service at http://localhost:8000. (${lastErrMsg})`
        );
      } else if (failures > 0) {
        setError(`Partial analytics loaded: some endpoints were unavailable (${lastErrMsg}).`);
      }
    } catch (err) {
      if (signal?.aborted) return;
      setError(`Backend error: ${(err as Error).message}`);
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadData(timeRange, controller.signal);

    return () => {
      controller.abort();
    };
  }, [timeRange, loadData]);

  // Derived peak hour from genuine hourly traffic
  const peakHour = useMemo(() => {
    if (!traffic?.hourly || traffic.hourly.length === 0) return null;
    return [...traffic.hourly].sort((a, b) => b.customers - a.customers)[0];
  }, [traffic]);

  // Derived max queue wait from genuine queue metrics
  const maxQueue = useMemo(() => {
    if (!queues?.queues || queues.queues.length === 0) return null;
    return [...queues.queues].sort((a, b) => b.avgWaitMinutes - a.avgWaitMinutes)[0];
  }, [queues]);

  // Derived section share from genuine dwell time sections
  const sectionShares = useMemo(() => {
    if (!dwell?.bySection || dwell.bySection.length === 0) return [];
    const totalMinutes = dwell.bySection.reduce((acc, s) => acc + s.minutes, 0);
    return dwell.bySection.map((item) => ({
      section: item.section,
      minutes: item.minutes,
      percentage: totalMinutes > 0 ? Math.round((item.minutes / totalMinutes) * 100) : 0,
    }));
  }, [dwell]);

  const customerVolumeDisplay =
    traffic?.totalCustomers != null
      ? traffic.totalCustomers.toLocaleString()
      : summary?.todayCustomers != null
      ? summary.todayCustomers.toLocaleString()
      : "—";

  const avgDwellDisplay =
    dwell?.averageDwellMinutes != null
      ? `${dwell.averageDwellMinutes} min`
      : summary?.avgDwellMinutes != null
      ? `${summary.avgDwellMinutes} min`
      : "—";

  return (
    <div className="space-y-5">
      {/* Editorial Page Header */}
      <PageHeader
        title="Customer Analytics &amp; Footfall Intelligence"
        description="Detailed analysis of in-store customer traffic trajectories, departmental dwell times, peak flow distributions, and checkout queue congestion."
        actions={
          <div className="flex items-center gap-2">
            <div
              className="flex items-center p-0.5 rounded-lg bg-[#f2f3ef] border border-[#e6e7e3]"
              role="group"
              aria-label="Select analytics timeframe"
            >
              {(
                [
                  { id: "today", label: "Today" },
                  { id: "7d", label: "7 Days" },
                  { id: "30d", label: "30 Days" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setTimeRange(tab.id)}
                  className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
                    timeRange === tab.id
                      ? "bg-white text-slate-900 shadow-2xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => loadData(timeRange)}
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
                onClick={() => loadData(timeRange)}
                className="rounded bg-rose-200/60 px-2 py-0.5 font-bold hover:bg-rose-200 text-rose-950 transition-colors"
              >
                Retry
              </button>
            </div>
          }
          onDismiss={() => setError(null)}
        />
      )}

      {/* Primary KPI Row */}
      {isLoading ? (
        <section aria-label="Loading customer metrics" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </section>
      ) : (
        <section aria-label="Customer traffic metrics" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
              <span>Customer Volume</span>
              <MaterialIcon name="groups" className="h-3.5 w-3.5 text-emerald-700" aria-hidden="true" />
            </div>
            <div className="mt-2.5 flex items-baseline gap-2">
              <span className="font-heading text-2xl font-extrabold text-slate-900 tabular-nums">
                {customerVolumeDisplay}
              </span>
              {summary?.todayCustomersDelta && (
                <span className="text-xs font-semibold text-emerald-800 tabular-nums">
                  {summary.todayCustomersDelta}
                </span>
              )}
            </div>
            <p className="mt-1 text-[11px] text-slate-400">Total detected visits for {timeRange}</p>
          </div>

          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
              <span>Avg Store Dwell</span>
              <MaterialIcon name="schedule" className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
            </div>
            <div className="mt-2.5 flex items-baseline gap-2">
              <span className="font-heading text-2xl font-extrabold text-slate-900 tabular-nums">
                {avgDwellDisplay}
              </span>
              {summary?.avgDwellDelta && (
                <span className="text-xs font-semibold text-slate-600 tabular-nums">
                  {summary.avgDwellDelta}
                </span>
              )}
            </div>
            <p className="mt-1 text-[11px] text-slate-400">Entry to checkout completion</p>
          </div>

          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
              <span>Peak Flow Window</span>
              <MaterialIcon name="trending_up" className="h-3.5 w-3.5 text-emerald-700" aria-hidden="true" />
            </div>
            <div className="mt-2.5 flex items-baseline gap-2">
              <span className="font-heading text-xl font-extrabold text-slate-900 tabular-nums">
                {peakHour ? `${peakHour.hour}:00 – ${String(Number(peakHour.hour) + 1).padStart(2, "0")}:00` : "—"}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-slate-400 tabular-nums">
              {peakHour ? `${peakHour.customers} visitors recorded` : "Awaiting hourly telemetry"}
            </p>
          </div>

          <div className="rounded-xl border border-amber-200/80 bg-amber-50/40 p-4">
            <div className="flex items-center justify-between text-xs font-medium text-amber-900">
              <span>Max Queue Wait</span>
              <MaterialIcon name="warning" className="h-3.5 w-3.5 text-amber-700" aria-hidden="true" />
            </div>
            <div className="mt-2.5 flex items-baseline gap-2">
              <span className="font-heading text-2xl font-extrabold text-amber-950 tabular-nums">
                {maxQueue ? `${maxQueue.avgWaitMinutes} min` : "—"}
              </span>
              <span className="text-xs font-bold text-amber-800">
                {maxQueue?.checkoutId || "Normal"}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-amber-800">
              {maxQueue ? `${maxQueue.currentQueue} visitors waiting` : "No queue congestion detected"}
            </p>
          </div>
        </section>
      )}

      {/* Traffic Trajectory and Hourly Distribution */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Daily Footfall Trajectory"
          description="Customer detections aggregated across store operating days"
        >
          {isLoading ? (
            <ChartSkeleton />
          ) : !traffic?.daily || traffic.daily.length === 0 ? (
            <EmptyState
              icon="groups"
              title="No daily traffic recorded"
              description={`No daily ingress telemetry returned for "${timeRange}".`}
            />
          ) : (
            <TrafficLineChart data={traffic.daily} />
          )}
        </ChartCard>

        <ChartCard
          title="Operating Hour Traffic Distribution"
          description="Customer density patterns across operational hours"
        >
          {isLoading ? (
            <ChartSkeleton />
          ) : !traffic?.hourly || traffic.hourly.length === 0 ? (
            <EmptyState
              icon="schedule"
              title="No hourly traffic recorded"
              description="Hourly ingress data has not been logged by computer-vision sensors."
            />
          ) : (
            <HourlyBarChart data={traffic.hourly} />
          )}
        </ChartCard>
      </div>

      {/* Dwell-Time Distribution & Departmental Footfall Share */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Average Dwell Duration by Department"
          description="Average time spent by shoppers in each designated section (minutes)"
          footer={dwell?.averageDwellMinutes ? `Storewide average dwell: ${dwell.averageDwellMinutes} min` : undefined}
        >
          {isLoading ? (
            <ChartSkeleton />
          ) : !dwell?.bySection || dwell.bySection.length === 0 ? (
            <EmptyState
              icon="storefront"
              title="No dwell-time telemetry"
              description="Departmental dwell time data is not currently available from the backend."
            />
          ) : (
            <div className="h-68 w-full" role="img" aria-label="Bar chart showing dwell time by store section">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dwell.bySection} margin={{ top: 10, right: 10, bottom: 4, left: -16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eeefec" vertical={false} />
                  <XAxis dataKey="section" tick={{ fontSize: 11, fill: "#858e9c" }} stroke="#e6e7e3" tickLine={false} />
                  <YAxis
                    unit="m"
                    tick={{ fontSize: 11, fill: "#858e9c" }}
                    width={38}
                    allowDecimals={false}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    formatter={(value: number | string | readonly (number | string)[] | undefined) => [
                      `${value ?? 0} minutes`,
                      "Avg Dwell",
                    ]}
                    contentStyle={{
                      borderRadius: "8px",
                      borderColor: "#e6e7e3",
                      fontSize: "12px",
                      backgroundColor: "#ffffff",
                      boxShadow: "0 1px 3px 0 rgb(0 0 0 / 0.05)",
                    }}
                  />
                  <Bar dataKey="minutes" name="Dwell Time" fill="#065f46" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </ChartCard>

        {/* Department Footfall Share */}
        <section
          aria-label="Department footfall share"
          className="rounded-xl border border-[#e6e7e3] bg-white p-4.5 flex flex-col justify-between"
        >
          <div>
            <div className="pb-3 border-b border-[#eeefec]">
              <h2 className="font-heading text-sm font-bold text-slate-900">
                Department Footfall Share
              </h2>
              <p className="text-xs text-slate-500">
                Proportion of in-store customer dwell duration recorded per zone
              </p>
            </div>

            {isLoading ? (
              <div className="space-y-3.5 pt-3 animate-pulse">
                <div className="h-6 bg-slate-100 rounded" />
                <div className="h-6 bg-slate-100 rounded" />
                <div className="h-6 bg-slate-100 rounded" />
              </div>
            ) : sectionShares.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-500">
                <MaterialIcon name="pie_chart" className="h-6 w-6 text-slate-400 mx-auto mb-1.5" aria-hidden="true" />
                <p className="font-semibold text-slate-700">No departmental data</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Section dwell breakdown has not been reported.</p>
              </div>
            ) : (
              <div className="space-y-3.5 pt-3">
                {sectionShares.map((item) => (
                  <div key={item.section} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-slate-800">{item.section}</span>
                      <div className="flex items-center gap-1.5 tabular-nums">
                        <span className="text-slate-500 text-[11px]">
                          {item.minutes} min ({item.percentage}%)
                        </span>
                      </div>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#f2f3ef]">
                      <div
                        className="h-full bg-emerald-800 rounded-full transition-all duration-300"
                        style={{ width: `${item.percentage}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mt-4 flex items-center gap-2 rounded-lg bg-[#fafaf8] border border-[#eeefec] p-2.5 text-xs text-slate-600">
            <MaterialIcon name="trending_up" className="h-3.5 w-3.5 text-emerald-800 shrink-0" aria-hidden="true" />
            <span>Telemetry calculated from overhead camera customer tracking.</span>
          </div>
        </section>
      </div>

      {/* Checkout Lane Queue & Wait Time Analysis */}
      <section
        aria-label="Checkout queue performance table"
        className="rounded-xl border border-[#e6e7e3] bg-white p-4.5 space-y-3"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 pb-2.5 border-b border-[#eeefec]">
          <div>
            <h2 className="font-heading text-sm font-bold text-slate-900">
              Checkout Queue Status &amp; Wait Time Analysis
            </h2>
            <p className="text-xs text-slate-500">
              Live register occupancy and estimated wait times monitored by overhead sensors
            </p>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            {queues?.updatedAt ? `Updated: ${queues.updatedAt}` : "Sampling: Live"}
          </span>
        </div>

        {isLoading ? (
          <TableSkeleton rows={3} />
        ) : !queues?.queues || queues.queues.length === 0 ? (
          <EmptyState
            icon="schedule"
            title="No checkout queue records"
            description="Checkout sensor telemetry is currently not reporting line lengths."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" aria-label="Checkout lane table">
              <thead className="border-b border-[#eeefec] bg-[#f8f8f6] text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="px-3.5 py-2">Checkout Lane</th>
                  <th className="px-3.5 py-2">Current Queue</th>
                  <th className="px-3.5 py-2">Estimated Wait</th>
                  <th className="px-3.5 py-2">Peak Queue</th>
                  <th className="px-3.5 py-2">Operating Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eeefec]">
                {queues.queues.map((q: QueuePoint) => {
                  const isCongested = q.currentQueue >= 4 || q.avgWaitMinutes >= 6;
                  const isBusy = q.currentQueue >= 2 || q.avgWaitMinutes >= 3;

                  return (
                    <tr key={q.checkoutId} className="hover:bg-[#fafaf8] transition-colors">
                      <td className="px-3.5 py-2.5 font-bold text-slate-900">
                        {q.checkoutId}
                      </td>
                      <td className="px-3.5 py-2.5 font-mono font-bold text-slate-800 tabular-nums">
                        {q.currentQueue} {q.currentQueue === 1 ? "shopper" : "shoppers"}
                      </td>
                      <td className="px-3.5 py-2.5 font-semibold text-slate-700 tabular-nums">
                        {q.avgWaitMinutes} min
                      </td>
                      <td className="px-3.5 py-2.5 font-mono text-slate-500 tabular-nums">
                        {q.peakQueue} max
                      </td>
                      <td className="px-3.5 py-2.5">
                        <StatusBadge
                          variant={isCongested ? "critical" : isBusy ? "warning" : "success"}
                          size="sm"
                        >
                          {isCongested ? "Congested" : isBusy ? "Moderate Wait" : "Normal Flow"}
                        </StatusBadge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
