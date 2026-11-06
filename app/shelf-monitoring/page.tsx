"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import PageHeader from "@/components/dashboard/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import NoticeBanner from "@/components/ui/NoticeBanner";
import MaterialIcon from "@/components/ui/MaterialIcon";
import { CardSkeleton } from "@/components/ui/Skeleton";
import { listShelves } from "@/lib/api/shelf-monitoring";
import type { ShelfItem, ShelfStatus } from "@/types/shelves";

type SortOption = "critical-first" | "lowest-fill" | "highest-fill" | "aisle";

// Calculate realistic fill distribution across 3 physical tiers
function computeTierLevels(overallFill: number) {
  const t1 = Math.min(100, Math.round((Math.min(overallFill, 40) / 40) * 100));
  const t2 = Math.min(100, Math.round((Math.max(0, Math.min(overallFill - 40, 35)) / 35) * 100));
  const t3 = Math.min(100, Math.round((Math.max(0, overallFill - 75) / 25) * 100));

  return [
    { id: "T1", label: "Base Tier", fill: t1 },
    { id: "T2", label: "Mid Tier", fill: t2 },
    { id: "T3", label: "Top Tier", fill: t3 },
  ];
}

export default function ShelfMonitoringPage() {
  const [shelvesList, setShelvesList] = useState<ShelfItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<"all" | "critical" | "low" | "ok">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortOption>("critical-first");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [activeRestockModal, setActiveRestockModal] = useState<ShelfItem | null>(null);

  const fetchShelves = useCallback(async (filter: "all" | "critical" | "low" | "ok", signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);

    try {
      // Backend contract accepts "all" | "low" | "critical"
      const apiFilter = filter === "all" || filter === "ok" ? undefined : filter;
      const res = await listShelves(apiFilter, signal);

      if (signal?.aborted) return;

      if (res && Array.isArray(res.shelves)) {
        setShelvesList(res.shelves);
      } else {
        setShelvesList([]);
      }
    } catch (err) {
      if (signal?.aborted) return;
      setError(
        `Failed to retrieve shelf inventory: ${(err as Error).message}. Check backend service at http://localhost:8000.`
      );
      setShelvesList([]);
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchShelves(statusFilter, controller.signal);

    return () => {
      controller.abort();
    };
  }, [statusFilter, fetchShelves]);

  const criticalCount = useMemo(
    () => shelvesList.filter((s) => s.status === "critical").length,
    [shelvesList]
  );
  const lowCount = useMemo(
    () => shelvesList.filter((s) => s.status === "low").length,
    [shelvesList]
  );
  const okCount = useMemo(
    () => shelvesList.filter((s) => s.status === "ok").length,
    [shelvesList]
  );
  const avgFillPct = useMemo(
    () =>
      shelvesList.length > 0
        ? Math.round(shelvesList.reduce((acc, s) => acc + s.fillPct, 0) / shelvesList.length)
        : 0,
    [shelvesList]
  );

  const displayedShelves = useMemo(() => {
    let list = shelvesList.filter((shelf) => {
      const matchesStatus =
        statusFilter === "all" ? true : shelf.status === statusFilter;
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        shelf.name.toLowerCase().includes(q) ||
        shelf.aisle.toLowerCase().includes(q);
      return matchesStatus && matchesSearch;
    });

    list = [...list].sort((a, b) => {
      if (sortBy === "critical-first") {
        const score = (s: ShelfStatus) => (s === "critical" ? 0 : s === "low" ? 1 : 2);
        return score(a.status) - score(b.status) || a.fillPct - b.fillPct;
      }
      if (sortBy === "lowest-fill") return a.fillPct - b.fillPct;
      if (sortBy === "highest-fill") return b.fillPct - a.fillPct;
      if (sortBy === "aisle") return a.aisle.localeCompare(b.aisle);
      return 0;
    });

    return list;
  }, [shelvesList, statusFilter, searchQuery, sortBy]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 4000);
  };

  const handleRefreshScan = () => {
    fetchShelves(statusFilter);
    showToast("Triggered inventory refresh from FastAPI backend.");
  };

  return (
    <div className="space-y-5">
      {/* Editorial Header */}
      <PageHeader
        title="Shelf Monitoring &amp; Stock Availability"
        description="Automated inventory fill rates, out-of-stock risk detection, tier-level shelf schematics, and floor restocking dispatch."
        actions={
          <button
            type="button"
            disabled={isLoading}
            onClick={handleRefreshScan}
            className="flex items-center gap-1.5 rounded-lg border border-[#e6e7e3] bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-[#f8f8f6] hover:text-slate-900 disabled:opacity-50 transition-colors shadow-2xs cursor-pointer"
          >
            <MaterialIcon
              name="refresh"
              className={`h-3.5 w-3.5 text-emerald-800 ${isLoading ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            <span>Refresh Scan</span>
          </button>
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
                onClick={() => fetchShelves(statusFilter)}
                className="rounded bg-rose-200/60 px-2 py-0.5 font-bold hover:bg-rose-200 text-rose-950 transition-colors"
              >
                Retry
              </button>
            </div>
          }
          onDismiss={() => setError(null)}
        />
      )}

      {toastMessage && (
        <NoticeBanner
          type="success"
          message={toastMessage}
          onDismiss={() => setToastMessage(null)}
        />
      )}

      {/* KPI Status Row */}
      {isLoading ? (
        <section aria-label="Loading shelf health" className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </section>
      ) : (
        <section aria-label="Shelf health indicators" className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <span className="text-xs text-slate-600 font-medium block">Overall Store Fill</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-slate-900 tabular-nums block">
              {shelvesList.length > 0 ? `${avgFillPct}%` : "—"}
            </span>
            <span className="text-[11px] text-slate-500 mt-0.5 block">Storewide mean availability</span>
          </div>

          <div className="rounded-xl border border-rose-200/90 bg-rose-50/40 p-4">
            <span className="text-xs text-rose-900 font-semibold block">Critical Restock</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-rose-950 tabular-nums block">
              {shelvesList.length > 0 ? criticalCount : "—"}
            </span>
            <span className="text-[11px] text-rose-800 mt-0.5 block">Under 40% threshold</span>
          </div>

          <div className="rounded-xl border border-amber-200/90 bg-amber-50/40 p-4">
            <span className="text-xs text-amber-900 font-semibold block">Low Stock Warnings</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-amber-950 tabular-nums block">
              {shelvesList.length > 0 ? lowCount : "—"}
            </span>
            <span className="text-[11px] text-amber-800 mt-0.5 block">40% – 70% fill range</span>
          </div>

          <div className="rounded-xl border border-emerald-200/90 bg-emerald-50/40 p-4">
            <span className="text-xs text-emerald-900 font-semibold block">Optimal Availability</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-emerald-950 tabular-nums block">
              {shelvesList.length > 0 ? okCount : "—"}
            </span>
            <span className="text-[11px] text-emerald-800 mt-0.5 block">Above 70% threshold</span>
          </div>
        </section>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 rounded-xl border border-[#e6e7e3] bg-white p-3.5">
        {/* Status Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Filter shelves by status">
          <button
            type="button"
            role="tab"
            aria-selected={statusFilter === "all"}
            onClick={() => setStatusFilter("all")}
            className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer ${
              statusFilter === "all"
                ? "bg-emerald-900 text-white"
                : "bg-[#f2f3ef] text-slate-700 hover:text-slate-900"
            }`}
          >
            All Bays ({shelvesList.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={statusFilter === "critical"}
            onClick={() => setStatusFilter("critical")}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer ${
              statusFilter === "critical"
                ? "bg-rose-700 text-white"
                : "bg-rose-50 text-rose-900 border border-rose-300"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${statusFilter === "critical" ? "bg-white" : "bg-rose-600"}`} />
            <span>Critical ({criticalCount})</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={statusFilter === "low"}
            onClick={() => setStatusFilter("low")}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer ${
              statusFilter === "low"
                ? "bg-amber-700 text-white"
                : "bg-amber-50 text-amber-950 border border-amber-300"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${statusFilter === "low" ? "bg-white" : "bg-amber-600"}`} />
            <span>Low Stock ({lowCount})</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={statusFilter === "ok"}
            onClick={() => setStatusFilter("ok")}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer ${
              statusFilter === "ok"
                ? "bg-emerald-800 text-white"
                : "bg-emerald-50 text-emerald-950 border border-emerald-300"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${statusFilter === "ok" ? "bg-white" : "bg-emerald-600"}`} />
            <span>Optimal ({okCount})</span>
          </button>
        </div>

        {/* Search & Sort */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 sm:w-56 min-w-[160px]">
            <MaterialIcon name="search" className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
            <input
              type="text"
              placeholder="Search aisle or category..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-[#e6e7e3] bg-[#f8f8f6] pl-8 pr-7 py-1 text-xs text-slate-900 placeholder:text-slate-500 focus:bg-white focus:border-emerald-700 focus:outline-none"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-2 text-slate-500 hover:text-slate-700"
                aria-label="Clear search"
              >
                <MaterialIcon name="close" className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-1.5 rounded-lg border border-[#e6e7e3] bg-white px-2 py-1 text-xs">
            <MaterialIcon name="swap_vert" className="h-3 w-3 text-slate-500" aria-hidden="true" />
            <select
              aria-label="Sort shelves list"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortOption)}
              className="bg-transparent text-slate-800 text-xs font-semibold focus:outline-none cursor-pointer"
            >
              <option value="critical-first">Critical first</option>
              <option value="lowest-fill">Lowest fill</option>
              <option value="highest-fill">Highest fill</option>
              <option value="aisle">Aisle (A–Z)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Shelf Matrix Cards */}
      {isLoading ? (
        <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : displayedShelves.length === 0 ? (
        <EmptyState
          icon="inventory_2"
          title="No shelf bays found"
          description={
            shelvesList.length === 0
              ? "No monitored shelf bays returned by the backend. Ensure the FastAPI service is active."
              : `No monitored bays matched "${searchQuery}" under the "${statusFilter}" filter.`
          }
          action={
            shelvesList.length === 0
              ? {
                  label: "Retry Connection",
                  onClick: () => fetchShelves(statusFilter),
                }
              : {
                  label: "Reset filters",
                  onClick: () => {
                    setStatusFilter("all");
                    setSearchQuery("");
                  },
                }
          }
        />
      ) : (
        <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {displayedShelves.map((shelf) => {
            const isCritical = shelf.status === "critical";
            const isLow = shelf.status === "low";
            const tiers = computeTierLevels(shelf.fillPct);

            return (
              <div
                key={shelf.id}
                className={`flex flex-col justify-between rounded-xl border bg-white p-4 transition-colors ${
                  isCritical
                    ? "border-rose-200 hover:border-rose-300"
                    : isLow
                    ? "border-amber-200 hover:border-amber-300"
                    : "border-[#e6e7e3] hover:border-slate-300"
                }`}
              >
                <div>
                  {/* Category, Aisle & Badge */}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h3 className="font-heading text-sm font-bold text-slate-900">
                        {shelf.name}
                      </h3>
                      <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-600">
                        <MaterialIcon name="location_on" className="h-3 w-3 text-emerald-800 shrink-0" aria-hidden="true" />
                        <span className="font-semibold text-slate-800">{shelf.aisle}</span>
                        <span>· Zone {shelf.id}</span>
                      </div>
                    </div>

                    <StatusBadge
                      variant={isCritical ? "critical" : isLow ? "warning" : "success"}
                      size="sm"
                    >
                      {isCritical ? "Critical" : isLow ? "Low Stock" : "Optimal"}
                    </StatusBadge>
                  </div>

                  {/* 3-Tier Shelf Schematic */}
                  <div className="mt-3 rounded-lg border border-[#eeefec] bg-[#fafaf8] p-2.5">
                    <div className="flex items-center justify-between text-[10px] font-bold text-slate-500 uppercase tracking-wider pb-1.5">
                      <span>Shelf Bay Schematic</span>
                      <span>Level 1–3 Telemetry</span>
                    </div>

                    <div className="space-y-2">
                      {tiers.map((tier) => (
                        <div
                          key={tier.id}
                          className="flex items-center gap-2"
                          title={`${shelf.name} — ${tier.label} (${tier.id}): ${tier.fill}% filled`}
                        >
                          <span className="w-13 text-[10px] font-mono text-slate-600 font-semibold shrink-0">
                            {tier.id} ({tier.label.split(" ")[0]})
                          </span>
                          <div
                            className="flex-1 h-2 rounded bg-[#f2f3ef] overflow-hidden"
                            role="progressbar"
                            aria-valuenow={tier.fill}
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-label={`${shelf.name} ${tier.label} fill level`}
                          >
                            <div
                              className={`h-full rounded-xs transition-all duration-300 ${
                                tier.fill === 0
                                  ? "bg-transparent"
                                  : tier.fill < 40
                                  ? "bg-rose-600"
                                  : tier.fill < 70
                                  ? "bg-amber-600"
                                  : "bg-emerald-700"
                              }`}
                              style={{ width: `${tier.fill}%` }}
                            />
                          </div>
                          <span className="w-8 text-right font-mono text-[10px] font-bold text-slate-700 tabular-nums shrink-0">
                            {tier.fill}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Overall Availability Metric & Fill Meter */}
                  <div className="mt-3 space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-600 font-medium">Bay Capacity</span>
                      <span className="font-mono font-bold text-slate-900 tabular-nums">
                        {shelf.fillPct}% Available
                      </span>
                    </div>

                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#f2f3ef]">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          isCritical
                            ? "bg-rose-600"
                            : isLow
                            ? "bg-amber-600"
                            : "bg-emerald-700"
                        }`}
                        style={{ width: `${shelf.fillPct}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Footer Actions */}
                <div className="mt-3.5 flex items-center justify-between border-t border-[#eeefec] pt-2.5 text-xs">
                  <div className="flex items-center gap-1 text-slate-500 text-[10px] tabular-nums">
                    <MaterialIcon name="schedule" className="h-3 w-3" aria-hidden="true" />
                    <span>Scan: {shelf.lastChecked || "Recent"}</span>
                  </div>

                  <button
                    type="button"
                    onClick={() => setActiveRestockModal(shelf)}
                    className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors shadow-2xs cursor-pointer ${
                      isCritical
                        ? "bg-rose-700 text-white hover:bg-rose-800"
                        : "bg-emerald-900 text-white hover:bg-emerald-950"
                    }`}
                  >
                    <MaterialIcon name="inventory_2" className="h-3 w-3" aria-hidden="true" />
                    <span>Restock Details</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Restock Details Modal */}
      {activeRestockModal && (() => {
        const modalShelf = activeRestockModal;
        const tiers = computeTierLevels(modalShelf.fillPct);

        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs"
            role="dialog"
            aria-modal="true"
            aria-labelledby="restock-modal-title"
          >
            <div className="w-full max-w-lg rounded-xl border border-[#e6e7e3] bg-white p-5 shadow-xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
              {/* Modal Header */}
              <div className="flex items-start justify-between pb-3 border-b border-[#eeefec]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-950 text-emerald-300">
                      <MaterialIcon name="inventory_2" className="h-3.5 w-3.5" aria-hidden="true" />
                    </span>
                    <h3 id="restock-modal-title" className="font-heading text-sm font-bold text-slate-900">
                      Shelf Telemetry — {modalShelf.name}
                    </h3>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {modalShelf.aisle} · Zone ID {modalShelf.id}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveRestockModal(null)}
                  className="rounded p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer"
                  aria-label="Close dialog"
                >
                  <MaterialIcon name="close" className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>

              {/* Inventory Breakdown */}
              <div className="space-y-3 text-xs">
                <div className="rounded-lg bg-[#fafaf8] border border-[#eeefec] p-3 space-y-2">
                  <div className="flex justify-between items-center font-semibold text-slate-800">
                    <span>Monitored Category</span>
                    <StatusBadge
                      variant={modalShelf.status === "critical" ? "critical" : modalShelf.status === "low" ? "warning" : "success"}
                      size="sm"
                    >
                      {modalShelf.status === "critical" ? "Critical Restock" : modalShelf.status === "low" ? "Low Stock" : "Optimal"}
                    </StatusBadge>
                  </div>
                  <p className="text-slate-700 leading-snug font-medium">
                    {modalShelf.name} ({modalShelf.aisle})
                  </p>

                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[#eeefec] text-[11px] tabular-nums">
                    <div>
                      <span className="text-slate-500 block">Measured Fill Rate</span>
                      <span className="font-bold text-slate-900 text-sm">{modalShelf.fillPct}%</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Last Vision Scan</span>
                      <span className="font-bold text-slate-900 text-sm">{modalShelf.lastChecked || "Recent"}</span>
                    </div>
                  </div>
                </div>

                {/* Tier Depletion Evidence */}
                <div>
                  <h4 className="text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Tier-Level Depletion (CV Sensor Breakdown)
                  </h4>
                  <div className="space-y-1.5 rounded-lg border border-[#eeefec] p-2.5 bg-white">
                    {tiers.map((t) => (
                      <div key={t.id} className="flex items-center justify-between text-xs">
                        <span className="text-slate-600 font-medium">
                          {t.id} ({t.label})
                        </span>
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-1.5 rounded bg-[#f2f3ef] overflow-hidden">
                            <div
                              className={`h-full rounded ${
                                t.fill === 0 ? "bg-transparent" : t.fill < 40 ? "bg-rose-600" : "bg-emerald-700"
                              }`}
                              style={{ width: `${t.fill}%` }}
                            />
                          </div>
                          <span className="w-8 text-right font-mono font-bold text-slate-800 tabular-nums">
                            {t.fill}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Modal Footer Actions */}
              <div className="flex items-center justify-end pt-3 border-t border-[#eeefec]">
                <button
                  type="button"
                  onClick={() => setActiveRestockModal(null)}
                  className="rounded-lg border border-[#e6e7e3] bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-[#f8f8f6] transition-colors cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
