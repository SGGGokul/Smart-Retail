"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import PageHeader from "@/components/dashboard/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import NoticeBanner from "@/components/ui/NoticeBanner";
import MaterialIcon from "@/components/ui/MaterialIcon";
import { CardSkeleton, TableSkeleton } from "@/components/ui/Skeleton";
import { listAlerts, updateAlert } from "@/lib/api/alerts";
import type { AlertItem } from "@/types/alerts";

export default function AlertsPage() {
  const [alertsList, setAlertsList] = useState<AlertItem[]>([]);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [ackFilter, setAckFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const fetchAlerts = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);

    try {
      const severityParam = severityFilter !== "all" ? severityFilter : undefined;
      const ackParam =
        ackFilter === "unacknowledged"
          ? false
          : ackFilter === "acknowledged"
          ? true
          : undefined;

      const res = await listAlerts(
        {
          severity: severityParam,
          acknowledged: ackParam,
        },
        signal
      );

      if (signal?.aborted) return;

      if (res && Array.isArray(res.alerts)) {
        setAlertsList(res.alerts);
      } else {
        setAlertsList([]);
      }
    } catch (err) {
      if (signal?.aborted) return;
      setError(
        `Unable to fetch alerts from backend: ${(err as Error).message}. Check FastAPI service at http://localhost:8000.`
      );
      setAlertsList([]);
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, [severityFilter, ackFilter]);

  useEffect(() => {
    const controller = new AbortController();
    fetchAlerts(controller.signal);

    return () => {
      controller.abort();
    };
  }, [fetchAlerts]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleToggleAcknowledge = async (id: string, description: string) => {
    const target = alertsList.find((a) => a.id === id);
    if (!target || updatingId) return;

    const newAckState = !target.acknowledged;
    setUpdatingId(id);

    try {
      const updated = await updateAlert(id, { acknowledged: newAckState });

      setAlertsList((prev) =>
        prev.map((alert) => (alert.id === id ? { ...alert, ...updated } : alert))
      );

      if (newAckState) {
        showToast(`Acknowledged incident "${description.slice(0, 40)}..."`);
      } else {
        showToast("Incident status reopened for observation.");
      }
    } catch (err) {
      showToast(`Failed to update alert status: ${(err as Error).message}`);
    } finally {
      setUpdatingId(null);
    }
  };

  const handleAcknowledgeAll = async () => {
    const unacknowledged = alertsList.filter((a) => !a.acknowledged);
    if (unacknowledged.length === 0) return;

    try {
      await Promise.all(
        unacknowledged.map((a) => updateAlert(a.id, { acknowledged: true }))
      );

      setAlertsList((prev) =>
        prev.map((alert) => ({ ...alert, acknowledged: true }))
      );

      showToast(`Acknowledged ${unacknowledged.length} active incidents.`);
    } catch (err) {
      showToast(`Failed to acknowledge all incidents: ${(err as Error).message}`);
    }
  };

  const criticalCount = useMemo(
    () => alertsList.filter((a) => a.severity === "critical").length,
    [alertsList]
  );
  const warningCount = useMemo(
    () => alertsList.filter((a) => a.severity === "warning").length,
    [alertsList]
  );
  const unackCount = useMemo(
    () => alertsList.filter((a) => !a.acknowledged).length,
    [alertsList]
  );

  const filteredAlerts = useMemo(() => {
    return alertsList.filter((alert) => {
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch =
        !q ||
        alert.area.toLowerCase().includes(q) ||
        alert.description.toLowerCase().includes(q) ||
        alert.type.toLowerCase().includes(q);

      return matchesSearch;
    });
  }, [alertsList, searchQuery]);

  return (
    <div className="space-y-5">
      {/* Header */}
      <PageHeader
        title="Alerts &amp; Incidents Feed"
        description="Operational incident stream, out-of-stock threshold triggers, queue wait-time anomalies, and CCTV hardware alerts."
        actions={
          <div className="flex items-center gap-2">
            {unackCount > 0 && (
              <button
                type="button"
                onClick={handleAcknowledgeAll}
                className="flex items-center gap-1.5 rounded-lg border border-[#e6e7e3] bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-[#f8f8f6] transition-colors shadow-2xs cursor-pointer"
              >
                <MaterialIcon name="done_all" className="h-3.5 w-3.5 text-emerald-800" aria-hidden="true" />
                <span>Acknowledge All ({unackCount})</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => fetchAlerts()}
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
                onClick={() => fetchAlerts()}
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
          type="info"
          message={toastMessage}
          onDismiss={() => setToastMessage(null)}
        />
      )}

      {/* KPI Severity Counters */}
      {isLoading ? (
        <section aria-label="Loading incident counters" className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </section>
      ) : (
        <section aria-label="Incident counters" className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <span className="text-xs text-slate-500 font-medium block">Total Incidents</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-slate-900 tabular-nums block">
              {alertsList.length}
            </span>
            <span className="text-[11px] text-slate-400 mt-0.5 block">Recorded events</span>
          </div>

          <div className="rounded-xl border border-amber-200/90 bg-amber-50/40 p-4">
            <span className="text-xs text-amber-900 font-medium block">Pending Review</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-amber-950 tabular-nums block">
              {unackCount}
            </span>
            <span className="text-[11px] text-amber-800 mt-0.5 block">Requires acknowledgement</span>
          </div>

          <div className="rounded-xl border border-rose-200/90 bg-rose-50/40 p-4">
            <span className="text-xs text-rose-900 font-medium block">Critical Urgency</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-rose-950 tabular-nums block">
              {criticalCount}
            </span>
            <span className="text-[11px] text-rose-800 mt-0.5 block">Immediate attention</span>
          </div>

          <div className="rounded-xl border border-[#e6e7e3] bg-white p-4">
            <span className="text-xs text-slate-500 font-medium block">Warnings &amp; Queue</span>
            <span className="mt-1 font-heading text-2xl font-extrabold text-slate-900 tabular-nums block">
              {warningCount}
            </span>
            <span className="text-[11px] text-slate-400 mt-0.5 block">Under observation</span>
          </div>
        </section>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 rounded-xl border border-[#e6e7e3] bg-white p-3.5">
        <div className="flex flex-wrap items-center gap-2">
          {/* Severity Filter */}
          <div className="flex items-center gap-1" role="group" aria-label="Filter by severity">
            <span className="text-[10px] font-bold text-slate-400 mr-1 uppercase tracking-wider">Severity:</span>
            {(["all", "critical", "warning", "info"] as const).map((sev) => (
              <button
                key={sev}
                type="button"
                onClick={() => setSeverityFilter(sev)}
                className={`rounded-md px-2 py-0.5 text-xs font-semibold capitalize transition-colors cursor-pointer ${
                  severityFilter === sev
                    ? "bg-emerald-900 text-white"
                    : "bg-[#f2f3ef] text-slate-600 hover:text-slate-900"
                }`}
              >
                {sev}
              </button>
            ))}
          </div>

          <div className="h-3.5 w-px bg-[#e6e7e3] hidden sm:block mx-1" />

          {/* Acknowledgement Status Filter */}
          <div className="flex items-center gap-1" role="group" aria-label="Filter by status">
            <span className="text-[10px] font-bold text-slate-400 mr-1 uppercase tracking-wider">Status:</span>
            <button
              type="button"
              onClick={() => setAckFilter("all")}
              className={`rounded-md px-2 py-0.5 text-xs font-semibold transition-colors cursor-pointer ${
                ackFilter === "all"
                  ? "bg-slate-900 text-white"
                  : "bg-[#f2f3ef] text-slate-600 hover:text-slate-900"
              }`}
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setAckFilter("unacknowledged")}
              className={`rounded-md px-2 py-0.5 text-xs font-semibold transition-colors cursor-pointer ${
                ackFilter === "unacknowledged"
                  ? "bg-amber-700 text-white"
                  : "bg-amber-50 text-amber-950 border border-amber-200/80"
              }`}
            >
              Pending ({unackCount})
            </button>
            <button
              type="button"
              onClick={() => setAckFilter("acknowledged")}
              className={`rounded-md px-2 py-0.5 text-xs font-semibold transition-colors cursor-pointer ${
                ackFilter === "acknowledged"
                  ? "bg-emerald-800 text-white"
                  : "bg-emerald-50 text-emerald-950 border border-emerald-200/80"
              }`}
            >
              Acknowledged
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="relative flex-1 sm:w-56 min-w-[160px]">
          <MaterialIcon name="search" className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
          <input
            type="text"
            placeholder="Search location or keyword..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-[#e6e7e3] bg-[#f8f8f6] pl-8 pr-7 py-1 text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-emerald-700 focus:outline-none"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-2 top-2 text-slate-400 hover:text-slate-600 cursor-pointer"
              aria-label="Clear search"
            >
              <MaterialIcon name="close" className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      {/* Incident Stream Table */}
      <section
        aria-label="Active incident table"
        className="rounded-xl border border-[#e6e7e3] bg-white p-4.5 space-y-3"
      >
        <div className="flex items-center justify-between pb-2.5 border-b border-[#eeefec]">
          <div>
            <h2 className="font-heading text-sm font-bold text-slate-900">
              Active Alerts ({filteredAlerts.length})
            </h2>
            <p className="text-xs text-slate-500">
              Filter by urgency level or click acknowledge to update status
            </p>
          </div>
          <span className="text-[11px] font-semibold text-slate-500 tabular-nums">
            {unackCount} pending review
          </span>
        </div>

        {isLoading ? (
          <TableSkeleton rows={4} />
        ) : filteredAlerts.length === 0 ? (
          <EmptyState
            icon="notifications_off"
            title="No alerts found"
            description={
              alertsList.length === 0
                ? "No alerts have been logged by the backend service."
                : "No incidents match the active search keyword or severity criteria."
            }
            action={{
              label: "Reset filters",
              onClick: () => {
                setSeverityFilter("all");
                setAckFilter("all");
                setSearchQuery("");
                fetchAlerts();
              },
            }}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" aria-label="Alerts feed table">
              <thead className="border-b border-[#eeefec] bg-[#f8f8f6] text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="px-3.5 py-2">Severity</th>
                  <th className="px-3.5 py-2">Alert Type</th>
                  <th className="px-3.5 py-2">Location</th>
                  <th className="px-3.5 py-2">Description</th>
                  <th className="px-3.5 py-2">Timestamp</th>
                  <th className="px-3.5 py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eeefec]">
                {filteredAlerts.map((alert) => (
                  <tr
                    key={alert.id}
                    className={`hover:bg-[#fafaf8] transition-colors ${
                      alert.acknowledged ? "opacity-70 bg-[#fafaf8]/50" : ""
                    }`}
                  >
                    <td className="px-3.5 py-2.5 whitespace-nowrap">
                      <StatusBadge
                        variant={
                          alert.severity === "critical"
                            ? "critical"
                            : alert.severity === "warning"
                            ? "warning"
                            : "info"
                        }
                        size="sm"
                      >
                        {alert.severity === "critical"
                          ? "Critical"
                          : alert.severity === "warning"
                          ? "Warning"
                          : "Info"}
                      </StatusBadge>
                    </td>
                    <td className="px-3.5 py-2.5 font-bold text-slate-900 whitespace-nowrap">
                      {alert.type}
                    </td>
                    <td className="px-3.5 py-2.5 text-xs font-semibold text-slate-700 whitespace-nowrap">
                      {alert.area}
                    </td>
                    <td className="px-3.5 py-2.5 text-xs text-slate-600 max-w-md">
                      {alert.description}
                    </td>
                    <td className="px-3.5 py-2.5 text-xs font-mono text-slate-400 whitespace-nowrap tabular-nums">
                      {alert.time}
                    </td>
                    <td className="px-3.5 py-2.5 text-right whitespace-nowrap">
                      <button
                        type="button"
                        disabled={updatingId === alert.id}
                        onClick={() => handleToggleAcknowledge(alert.id, alert.description)}
                        className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors shadow-2xs cursor-pointer disabled:opacity-50 ${
                          alert.acknowledged
                            ? "bg-[#f2f3ef] text-slate-600 hover:bg-slate-200"
                            : "bg-emerald-900 text-white hover:bg-emerald-950"
                        }`}
                      >
                        {updatingId === alert.id ? (
                          <>
                            <MaterialIcon name="refresh" className="h-3 w-3 animate-spin" aria-hidden="true" />
                            <span>Updating...</span>
                          </>
                        ) : alert.acknowledged ? (
                          <>
                            <MaterialIcon name="restart_alt" className="h-3 w-3" aria-hidden="true" />
                            <span>Reopen</span>
                          </>
                        ) : (
                          <>
                            <MaterialIcon name="check" className="h-3 w-3" aria-hidden="true" />
                            <span>Acknowledge</span>
                          </>
                        )}
                      </button>
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
