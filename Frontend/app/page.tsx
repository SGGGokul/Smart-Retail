"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import PageHeader from "@/components/dashboard/PageHeader";
import OperationalMetrics from "@/components/dashboard/OperationalMetrics";
import InsightsPanel from "@/components/dashboard/InsightsPanel";
import RecentEvents from "@/components/dashboard/RecentEvents";
import ShelfSummary from "@/components/dashboard/ShelfSummary";
import HourlyBarChart from "@/components/charts/HourlyBarChart";
import TrafficLineChart from "@/components/charts/TrafficLineChart";
import ChartCard from "@/components/ui/ChartCard";
import MaterialIcon from "@/components/ui/MaterialIcon";
import EmptyState from "@/components/ui/EmptyState";
import NoticeBanner from "@/components/ui/NoticeBanner";
import { ChartSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import {
  getDashboardSummary,
  getDashboardTraffic,
  getDashboardEvents,
  getDashboardShelves,
} from "@/lib/api/dashboard";
import type { AnalyticsSummaryResponse } from "@/types/dashboard";
import type { AnalyticsTrafficResponse } from "@/types/analytics";
import type { ShelfItem } from "@/types/shelves";
import type { AlertItem } from "@/types/alerts";

type Timeframe = "today" | "7d" | "30d";

export default function OverviewPage() {
  const [period, setPeriod] = useState<Timeframe>("7d");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [summary, setSummary] = useState<AnalyticsSummaryResponse | null>(null);
  const [traffic, setTraffic] = useState<AnalyticsTrafficResponse | null>(null);
  const [events, setEvents] = useState<AlertItem[]>([]);
  const [shelves, setShelves] = useState<ShelfItem[]>([]);

  const loadDashboardData = useCallback(async (selectedPeriod: Timeframe, signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);

    try {
      const [summaryRes, trafficRes, eventsRes, shelvesRes] = await Promise.allSettled([
        getDashboardSummary(signal),
        getDashboardTraffic(selectedPeriod, signal),
        getDashboardEvents(signal),
        getDashboardShelves(signal),
      ]);

      if (signal?.aborted) return;

      let errorCount = 0;
      let lastErrorMessage = "";

      if (summaryRes.status === "fulfilled") {
        setSummary(summaryRes.value);
      } else {
        errorCount++;
        lastErrorMessage = summaryRes.reason?.message || "Failed to load summary";
      }

      if (trafficRes.status === "fulfilled") {
        setTraffic(trafficRes.value);
      } else {
        errorCount++;
        lastErrorMessage = trafficRes.reason?.message || "Failed to load traffic";
      }

      if (eventsRes.status === "fulfilled") {
        setEvents(eventsRes.value.alerts || []);
      } else {
        errorCount++;
        lastErrorMessage = eventsRes.reason?.message || "Failed to load alerts";
      }

      if (shelvesRes.status === "fulfilled") {
        setShelves(shelvesRes.value.shelves || []);
      } else {
        errorCount++;
        lastErrorMessage = shelvesRes.reason?.message || "Failed to load shelves";
      }

      if (errorCount === 4) {
        setError(
          `Unable to connect to FastAPI backend service. Ensure the server is running on http://localhost:8000. (${lastErrorMessage})`
        );
      } else if (errorCount > 0) {
        setError(`Partial data loaded: some dashboard endpoints were unavailable (${lastErrorMessage}).`);
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
    loadDashboardData(period, controller.signal);

    return () => {
      controller.abort();
    };
  }, [period, loadDashboardData]);

  const activeIncidentCount = events.filter((e) => !e.acknowledged).length;

  return (
    <div className="space-y-5">
      {/* Editorial Header */}
      <PageHeader
        title="Store Intelligence"
        description="Operations telemetry, computer-vision detection metrics, and in-store inventory replenishment priorities."
        actions={
          <div className="flex items-center gap-2">
            {/* Timeframe Scope Selector */}
            <div
              className="flex items-center p-0.5 rounded-lg bg-[#f2f3ef] border border-[#e6e7e3]"
              role="group"
              aria-label="Select overview timeframe"
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
                  onClick={() => setPeriod(tab.id)}
                  className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${
                    period === tab.id
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
              onClick={() => loadDashboardData(period)}
              disabled={isLoading}
              className="flex items-center gap-1 rounded-lg border border-[#e6e7e3] bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-[#f8f8f6] disabled:opacity-50 transition-colors shadow-2xs"
              title="Refresh dashboard data"
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
                onClick={() => loadDashboardData(period)}
                className="rounded bg-rose-200/60 px-2 py-0.5 font-bold hover:bg-rose-200 text-rose-950 transition-colors"
              >
                Retry Request
              </button>
            </div>
          }
          onDismiss={() => setError(null)}
        />
      )}

      {/* Primary Operational Metrics */}
      <OperationalMetrics summary={summary} timeframe={period} isLoading={isLoading} />

      {/* Actionable Operational Insights Panel */}
      <InsightsPanel summary={summary} isLoading={isLoading} />

      {/* Primary Visualizations: Footfall Trend */}
      <div className="grid gap-4 lg:grid-cols-12">
        <ChartCard
          title="Customer Footfall Volume &amp; Trend"
          description="Daily visitor detections from camera ingress points"
          className="lg:col-span-8"
        >
          {isLoading ? (
            <ChartSkeleton />
          ) : !traffic?.daily || traffic.daily.length === 0 ? (
            <EmptyState
              icon="groups"
              title="No footfall records available"
              description={`No daily customer traffic has been recorded for the "${period}" timeframe.`}
              action={{
                label: "Retry",
                onClick: () => loadDashboardData(period),
              }}
            />
          ) : (
            <TrafficLineChart data={traffic.daily} />
          )}
        </ChartCard>

        <section
          aria-label="Recent store operational incidents"
          className="lg:col-span-4 rounded-xl border border-[#e6e7e3] bg-white p-4.5 flex flex-col justify-between"
        >
          <div>
            <div className="mb-3 flex items-center justify-between pb-2.5 border-b border-[#eeefec]">
              <div>
                <h2 className="font-heading text-sm font-bold text-slate-900">
                  Incident Feed
                </h2>
                <p className="text-[11px] text-slate-400">Real-time floor events</p>
              </div>
              <Link
                href="/alerts"
                className="text-xs font-semibold text-emerald-800 hover:text-emerald-950 transition-colors flex items-center gap-1"
              >
                <span>View all</span>
                <MaterialIcon name="arrow_forward" className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>

            {isLoading ? (
              <TableSkeleton rows={4} />
            ) : events.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-500">
                <MaterialIcon name="check_circle" className="h-5 w-5 text-emerald-600 mx-auto mb-1" aria-hidden="true" />
                <p className="font-semibold text-slate-700">No active incidents</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Floor operations are running smoothly.</p>
              </div>
            ) : (
              <RecentEvents events={events.slice(0, 4)} />
            )}
          </div>

          <div className="mt-3 pt-2.5 border-t border-[#eeefec] flex items-center justify-between text-[11px] text-slate-400">
            <span>Filter by priority in Alerts</span>
            <span className="font-mono text-[10px]">
              {activeIncidentCount} {activeIncidentCount === 1 ? "active" : "active"}
            </span>
          </div>
        </section>
      </div>

      {/* Secondary Visualizations: Hourly Curve + Shelf Replenishment Priority */}
      <div className="grid gap-4 lg:grid-cols-12">
        <ChartCard
          title="Hourly Visitor Density Distribution"
          description="Customer traffic curves during standard operating hours"
          className="lg:col-span-7"
        >
          {isLoading ? (
            <ChartSkeleton />
          ) : !traffic?.hourly || traffic.hourly.length === 0 ? (
            <EmptyState
              icon="schedule"
              title="No hourly traffic data"
              description="No hourly visitor ingress distribution available from computer-vision nodes."
            />
          ) : (
            <HourlyBarChart data={traffic.hourly} />
          )}
        </ChartCard>

        <section
          aria-label="Aisle shelf stock availability"
          className="lg:col-span-5 rounded-xl border border-[#e6e7e3] bg-white p-4.5 flex flex-col justify-between"
        >
          <div>
            <div className="mb-3 pb-2.5 border-b border-[#eeefec] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[#f2f3ef] text-slate-700">
                  <MaterialIcon name="layers" className="h-3.5 w-3.5" aria-hidden="true" />
                </div>
                <div>
                  <h2 className="font-heading text-sm font-bold text-slate-900">
                    Aisle Stock Levels
                  </h2>
                  <p className="text-[11px] text-slate-400">
                    Automated vision fill analysis
                  </p>
                </div>
              </div>

              <Link
                href="/shelf-monitoring"
                className="text-xs font-semibold text-emerald-800 hover:text-emerald-950 transition-colors flex items-center gap-1"
              >
                <span>Matrix</span>
                <MaterialIcon name="arrow_forward" className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>

            {isLoading ? (
              <TableSkeleton rows={4} />
            ) : shelves.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-500">
                <MaterialIcon name="inventory_2" className="h-5 w-5 text-slate-400 mx-auto mb-1" aria-hidden="true" />
                <p className="font-semibold text-slate-700">No shelf telemetry</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Camera shelf detection has not returned data.</p>
              </div>
            ) : (
              <ShelfSummary items={shelves.slice(0, 4)} />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
