"use client";

import { useState, useEffect, useCallback } from "react";
import PageHeader from "@/components/dashboard/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import NoticeBanner from "@/components/ui/NoticeBanner";
import MaterialIcon from "@/components/ui/MaterialIcon";
import { checkHealth } from "@/lib/api/system";
import type { HealthResponse } from "@/types/system";

interface AppSettings {
  storeBranch: string;
  refreshIntervalSeconds: number;
  compactDensity: boolean;
  chartAnimations: boolean;
  criticalShelfThresholdPct: number;
  queueAlertThresholdMinutes: number;
  apiBaseUrl: string;
}

const DEFAULT_SETTINGS: AppSettings = {
  storeBranch: "Store #104 — Downtown Branch",
  refreshIntervalSeconds: 30,
  compactDensity: false,
  chartAnimations: true,
  criticalShelfThresholdPct: 40,
  queueAlertThresholdMinutes: 5,
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
};

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const probeBackendHealth = useCallback(async (signal?: AbortSignal) => {
    setIsTesting(true);
    setHealthError(null);
    try {
      const health = await checkHealth(signal);
      setHealthData(health);
    } catch (err) {
      setHealthData(null);
      setHealthError((err as Error).message);
    } finally {
      setIsTesting(false);
    }
  }, []);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("retailiq_frontend_settings");
      if (saved) {
        const parsed = JSON.parse(saved);
        queueMicrotask(() => {
          setSettings(parsed);
        });
      }
    } catch {
      // LocalStorage unavailable
    }

    const controller = new AbortController();
    queueMicrotask(() => {
      probeBackendHealth(controller.signal);
    });

    return () => {
      controller.abort();
    };
  }, [probeBackendHealth]);

  const handleSave = () => {
    try {
      localStorage.setItem("retailiq_frontend_settings", JSON.stringify(settings));
      setSaveNotice("Preferences saved successfully to browser local storage.");
    } catch {
      setSaveNotice("Preferences updated for the current session.");
    }

    setTimeout(() => {
      setSaveNotice(null);
    }, 3500);
  };

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS);
    try {
      localStorage.removeItem("retailiq_frontend_settings");
    } catch {
      // ignore
    }
    setSaveNotice("Preferences reset to defaults.");
    setTimeout(() => {
      setSaveNotice(null);
    }, 3000);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <PageHeader
        title="Settings &amp; System Telemetry"
        description="FastAPI service health, model inference status, store configuration parameters, and telemetry thresholds."
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-1 rounded-lg border border-[#e6e7e3] bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-[#f8f8f6] transition-colors shadow-2xs cursor-pointer"
            >
              <MaterialIcon name="restart_alt" className="h-3 w-3" aria-hidden="true" />
              <span>Reset</span>
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="inline-flex items-center gap-1 rounded-lg bg-emerald-900 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-950 transition-colors shadow-2xs cursor-pointer"
            >
              <MaterialIcon name="save" className="h-3 w-3" aria-hidden="true" />
              <span>Save</span>
            </button>
          </div>
        }
      />

      {saveNotice && (
        <NoticeBanner
          type="success"
          message={saveNotice}
          onDismiss={() => setSaveNotice(null)}
        />
      )}

      {/* Backend Health & Telemetry Status */}
      <section
        aria-label="FastAPI backend connectivity"
        className="rounded-xl border border-[#e6e7e3] bg-white p-4.5 space-y-4"
      >
        <div className="flex items-center justify-between border-b border-[#eeefec] pb-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#f2f3ef] text-slate-800">
              <MaterialIcon name="database" className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <h2 className="font-heading text-sm font-bold text-slate-900">
                FastAPI Backend Service Target
              </h2>
              <p className="text-[11px] text-slate-400">
                Liveness endpoint conforming to API_CONTRACT.md (GET /health)
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge
              variant={healthData?.status === "ok" ? "success" : "critical"}
              size="sm"
            >
              {healthData?.status === "ok" ? "Backend Connected" : "Backend Offline"}
            </StatusBadge>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 text-xs">
          <div className="space-y-2">
            <label htmlFor="api-base-url" className="font-bold text-slate-800 block">
              API Base URL
            </label>
            <p className="text-[11px] text-slate-400">
              Configured via environment variable <code className="font-mono text-slate-700">NEXT_PUBLIC_API_BASE_URL</code>
            </p>
            <div className="flex items-center gap-2 pt-0.5">
              <input
                id="api-base-url"
                type="text"
                value={settings.apiBaseUrl}
                onChange={(e) => setSettings({ ...settings, apiBaseUrl: e.target.value })}
                className="flex-1 rounded-lg border border-[#e6e7e3] bg-[#f8f8f6] px-3 py-1.5 font-mono text-xs text-slate-900 focus:bg-white focus:border-emerald-700 focus:outline-none"
              />
              <button
                type="button"
                disabled={isTesting}
                onClick={() => probeBackendHealth()}
                className="rounded-lg border border-[#e6e7e3] bg-[#f2f3ef] px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-white transition-colors disabled:opacity-50 shrink-0 shadow-2xs cursor-pointer"
              >
                {isTesting ? "Testing..." : "Test Health"}
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <span className="font-bold text-slate-800 block">Service Diagnostics</span>
            <div className="rounded-lg border border-[#e6e7e3] bg-[#fafaf8] p-3 text-xs space-y-1.5">
              {healthData ? (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Service Status:</span>
                    <span className="font-bold text-emerald-800 uppercase text-[11px]">{healthData.status}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Backend Version:</span>
                    <span className="font-mono font-bold text-slate-900">{healthData.version}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Server Uptime:</span>
                    <span className="font-mono font-bold text-slate-900">{formatUptime(healthData.uptimeSeconds)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-500">Last Ping:</span>
                    <span className="font-mono text-[10px] text-slate-500">{healthData.timestamp}</span>
                  </div>
                </>
              ) : (
                <div className="text-slate-500">
                  <p className="font-semibold text-rose-800">No active connection to backend</p>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {healthError || "Run `python -m uvicorn ...` on port 8000 to enable live computer-vision and telemetry."}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Backend Telemetry Requirements Identified */}
        <div className="mt-4 pt-4 border-t border-[#eeefec]">
          <h3 className="font-heading text-xs font-bold text-slate-900 mb-2">
            Hardware &amp; Model Telemetry Status
          </h3>
          <p className="text-[11px] text-slate-500 mb-3">
            Only actual metrics exposed by the backend are presented below. Unimplemented telemetry fields are documented as backend integration requirements.
          </p>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="rounded-lg border border-[#e6e7e3] p-3 bg-[#fafaf8]">
              <span className="text-[10px] text-slate-400 block font-bold uppercase tracking-wider">YOLOv11 Inference</span>
              <span className="mt-1 font-semibold text-slate-700 block">
                {healthData ? "Active (Via /videos)" : "Unavailable"}
              </span>
              <span className="text-[10px] text-slate-400 mt-0.5 block">Managed by CV Worker</span>
            </div>

            <div className="rounded-lg border border-[#e6e7e3] p-3 bg-[#fafaf8]">
              <span className="text-[10px] text-slate-400 block font-bold uppercase tracking-wider">ByteTrack Tracker</span>
              <span className="mt-1 font-semibold text-slate-700 block">
                {healthData ? "Active (Via /videos)" : "Unavailable"}
              </span>
              <span className="text-[10px] text-slate-400 mt-0.5 block">Trajectory Processor</span>
            </div>

            <div className="rounded-lg border border-[#e6e7e3] p-3 bg-[#fafaf8]">
              <span className="text-[10px] text-slate-400 block font-bold uppercase tracking-wider">GPU Utilization</span>
              <span className="mt-1 font-mono text-slate-500 block">Not exposed</span>
              <span className="text-[10px] text-amber-800 mt-0.5 block">Endpoint requirement</span>
            </div>

            <div className="rounded-lg border border-[#e6e7e3] p-3 bg-[#fafaf8]">
              <span className="text-[10px] text-slate-400 block font-bold uppercase tracking-wider">CPU / Memory</span>
              <span className="mt-1 font-mono text-slate-500 block">Not exposed</span>
              <span className="text-[10px] text-amber-800 mt-0.5 block">Endpoint requirement</span>
            </div>
          </div>
        </div>
      </section>

      {/* Grid: Store Info & Telemetry Thresholds */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Store & Display Configuration */}
        <section
          aria-label="Store details & display settings"
          className="rounded-xl border border-[#e6e7e3] bg-white p-4.5 space-y-4"
        >
          <div className="flex items-center gap-2.5 border-b border-[#eeefec] pb-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#f2f3ef] text-slate-800">
              <MaterialIcon name="storefront" className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <h2 className="font-heading text-sm font-bold text-slate-900">
                Store Branch &amp; Refresh
              </h2>
              <p className="text-[11px] text-slate-400">Branch identification and refresh cadence</p>
            </div>
          </div>

          <div className="space-y-3.5 text-xs">
            <div>
              <label htmlFor="store-branch" className="font-bold text-slate-800 block">
                Store Branch Name
              </label>
              <input
                id="store-branch"
                type="text"
                value={settings.storeBranch}
                onChange={(e) => setSettings({ ...settings, storeBranch: e.target.value })}
                className="mt-1 w-full rounded-lg border border-[#e6e7e3] bg-[#f8f8f6] px-3 py-1.5 text-xs text-slate-900 focus:bg-white focus:border-emerald-700 focus:outline-none"
              />
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pt-2 border-t border-[#eeefec]">
              <div>
                <label htmlFor="refresh-interval" className="font-bold text-slate-800 block">
                  Dashboard Polling Cadence
                </label>
                <p className="text-[11px] text-slate-400">
                  Refresh interval for store telemetry views
                </p>
              </div>
              <select
                id="refresh-interval"
                value={settings.refreshIntervalSeconds}
                onChange={(e) =>
                  setSettings({ ...settings, refreshIntervalSeconds: Number(e.target.value) })
                }
                className="rounded-lg border border-[#e6e7e3] bg-white px-2.5 py-1 text-xs font-semibold text-slate-800 focus:border-emerald-700 focus:outline-none cursor-pointer"
              >
                <option value={15}>15 seconds</option>
                <option value={30}>30 seconds (Default)</option>
                <option value={60}>60 seconds</option>
              </select>
            </div>

            <div className="flex items-center justify-between pt-2.5 border-t border-[#eeefec]">
              <div>
                <span className="font-bold text-slate-800 block">Chart Transition Animations</span>
                <p className="text-[11px] text-slate-400">
                  Smooth interpolation across Recharts data points
                </p>
              </div>
              <input
                type="checkbox"
                checked={settings.chartAnimations}
                onChange={(e) => setSettings({ ...settings, chartAnimations: e.target.checked })}
                className="h-4 w-4 rounded border-slate-300 text-emerald-800 focus:ring-emerald-700 cursor-pointer accent-emerald-800"
              />
            </div>
          </div>
        </section>

        {/* Telemetry Alert Thresholds */}
        <section
          aria-label="Alert sensitivity thresholds"
          className="rounded-xl border border-[#e6e7e3] bg-white p-4.5 space-y-4"
        >
          <div className="flex items-center gap-2.5 border-b border-[#eeefec] pb-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#f2f3ef] text-slate-800">
              <MaterialIcon name="tune" className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <h2 className="font-heading text-sm font-bold text-slate-900">
                Operational Alert Thresholds
              </h2>
              <p className="text-[11px] text-slate-400">Configure sensitivity for stock and queue warnings</p>
            </div>
          </div>

          <div className="space-y-3.5 text-xs">
            <div>
              <div className="flex justify-between items-center">
                <label htmlFor="shelf-threshold" className="font-bold text-slate-800">
                  Critical Shelf Restock Level
                </label>
                <span className="font-mono font-bold text-rose-800 bg-rose-50 px-2 py-0.5 rounded border border-rose-200 tabular-nums">
                  {settings.criticalShelfThresholdPct}%
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Triggers priority notification when aisle fill drops below this percentage
              </p>
              <input
                id="shelf-threshold"
                type="range"
                min={20}
                max={60}
                step={5}
                value={settings.criticalShelfThresholdPct}
                onChange={(e) =>
                  setSettings({ ...settings, criticalShelfThresholdPct: Number(e.target.value) })
                }
                className="w-full mt-2 accent-emerald-800 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-400 font-mono pt-0.5">
                <span>20% (Conservative)</span>
                <span>40% (Default)</span>
                <span>60% (Aggressive)</span>
              </div>
            </div>

            <div className="pt-2.5 border-t border-[#eeefec]">
              <div className="flex justify-between items-center">
                <label htmlFor="queue-threshold" className="font-bold text-slate-800">
                  Queue Congestion Wait Time
                </label>
                <span className="font-mono font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 tabular-nums">
                  {settings.queueAlertThresholdMinutes} min
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Flags checkout register as congested if average wait exceeds threshold
              </p>
              <input
                id="queue-threshold"
                type="range"
                min={2}
                max={15}
                step={1}
                value={settings.queueAlertThresholdMinutes}
                onChange={(e) =>
                  setSettings({ ...settings, queueAlertThresholdMinutes: Number(e.target.value) })
                }
                className="w-full mt-2 accent-emerald-800 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-400 font-mono pt-0.5">
                <span>2 min</span>
                <span>5 min (Default)</span>
                <span>15 min</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
