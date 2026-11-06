"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import RetailIQLogo from "./RetailIQLogo";
import MaterialIcon from "@/components/ui/MaterialIcon";
import { checkHealth } from "@/lib/api/system";
import { listAlerts } from "@/lib/api/alerts";

interface TopnavProps {
  onMenuClick: () => void;
}

const ROUTE_TITLES: Record<string, { section: string; title: string }> = {
  "/": { section: "Intelligence", title: "Overview" },
  "/video-analytics": { section: "Intelligence", title: "Video Analytics" },
  "/customer-analytics": { section: "Intelligence", title: "Customer Analytics" },
  "/shelf-monitoring": { section: "Intelligence", title: "Shelf Monitoring" },
  "/alerts": { section: "Operations", title: "Alerts & Events" },
  "/ai-assistant": { section: "Operations", title: "RetailIQ Copilot" },
  "/reports": { section: "Operations", title: "Reports" },
  "/settings": { section: "System", title: "Settings" },
};

export default function Topnav({ onMenuClick }: TopnavProps) {
  const pathname = usePathname();
  const routeMeta = ROUTE_TITLES[pathname] || { section: "RetailIQ", title: "Dashboard" };

  const [selectedBranch, setSelectedBranch] = useState("Store #104 — Downtown");
  const [branchDropdownOpen, setBranchDropdownOpen] = useState(false);
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isBackendOnline, setIsBackendOnline] = useState<boolean | null>(null);
  const [unackAlertsCount, setUnackAlertsCount] = useState<number>(0);

  useEffect(() => {
    const controller = new AbortController();

    checkHealth(controller.signal)
      .then((health) => {
        setIsBackendOnline(health.status === "ok");
      })
      .catch(() => {
        setIsBackendOnline(false);
      });

    listAlerts({ acknowledged: false }, controller.signal)
      .then((data) => {
        setUnackAlertsCount(data.unacknowledgedCount ?? (data.alerts ? data.alerts.length : 0));
      })
      .catch(() => {
        setUnackAlertsCount(0);
      });

    return () => {
      controller.abort();
    };
  }, [pathname]);

  return (
    <header className="sticky top-0 z-30 flex h-15 shrink-0 items-center justify-between border-b border-[#e6e7e3] bg-white/95 px-4 sm:px-6 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open navigation menu"
          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 lg:hidden cursor-pointer"
        >
          <MaterialIcon name="menu" className="h-5 w-5" aria-hidden="true" />
        </button>

        <span className="lg:hidden">
          <RetailIQLogo collapsed />
        </span>

        <nav aria-label="Breadcrumb" className="hidden lg:flex items-center gap-1.5 text-xs">
          <Link
            href="/"
            className="font-medium text-slate-500 hover:text-slate-900 transition-colors"
          >
            RetailIQ
          </Link>
          <MaterialIcon name="chevron_right" className="h-3 w-3 text-slate-300" aria-hidden="true" />
          <span className="text-slate-400">{routeMeta.section}</span>
          <MaterialIcon name="chevron_right" className="h-3 w-3 text-slate-300" aria-hidden="true" />
          <span className="font-semibold text-slate-900">{routeMeta.title}</span>
        </nav>
      </div>

      <div className="hidden md:flex items-center flex-1 max-w-sm mx-6">
        <div className="relative w-full">
          <MaterialIcon name="search" className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search shelves, alerts, cameras..."
            className="w-full h-8 rounded-lg border border-[#e6e7e3] bg-[#f8f8f6] pl-8 pr-12 text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-emerald-700 focus:outline-none focus:ring-1 focus:ring-emerald-700 transition-colors"
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-0.5 pointer-events-none text-[10px] text-slate-400 bg-white border border-[#e6e7e3] px-1 py-0.2 rounded font-mono">
            <span>⌘K</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <div className="relative">
          <button
            type="button"
            onClick={() => setBranchDropdownOpen(!branchDropdownOpen)}
            className="hidden sm:flex items-center gap-1.5 rounded-lg border border-[#e6e7e3] bg-[#f8f8f6] px-2.5 py-1 text-xs font-medium text-slate-800 hover:bg-white hover:border-slate-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 shrink-0 cursor-pointer"
          >
            <MaterialIcon name="storefront" className="h-3.5 w-3.5 text-emerald-700 shrink-0" aria-hidden="true" />
            <span className="max-w-[220px] truncate">{selectedBranch}</span>
            <MaterialIcon name="expand_more" className="h-3.5 w-3.5 text-slate-500 ml-0.5 shrink-0" aria-hidden="true" />
          </button>

          {branchDropdownOpen && (
            <div
              className="absolute right-0 mt-1 w-54 rounded-lg border border-[#e6e7e3] bg-white py-1 shadow-md z-50 text-xs"
              onMouseLeave={() => setBranchDropdownOpen(false)}
            >
              <div className="px-3 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Select Store Branch
              </div>
              {[
                "Store #104 — Downtown",
                "Store #202 — Metro Mall",
                "Store #315 — Suburb West",
              ].map((branch) => (
                <button
                  key={branch}
                  type="button"
                  onClick={() => {
                    setSelectedBranch(branch);
                    setBranchDropdownOpen(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 hover:bg-[#f8f8f6] transition-colors cursor-pointer ${
                    selectedBranch === branch
                      ? "text-emerald-800 font-semibold bg-emerald-50/60"
                      : "text-slate-700"
                  }`}
                >
                  {branch}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Live Backend Connection Indicator */}
        <div
          role="status"
          aria-label={`FastAPI service status: ${isBackendOnline ? "online" : "offline"}`}
          className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
            isBackendOnline === true
              ? "border-emerald-200/80 bg-emerald-50/70 text-emerald-950"
              : isBackendOnline === false
              ? "border-amber-200/80 bg-amber-50/70 text-amber-950"
              : "border-slate-200 bg-slate-50 text-slate-700"
          }`}
        >
          <span className="relative flex h-1.5 w-1.5">
            {isBackendOnline && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
            )}
            <span
              className={`relative inline-flex h-1.5 w-1.5 rounded-full ${
                isBackendOnline === true
                  ? "bg-emerald-600"
                  : isBackendOnline === false
                  ? "bg-amber-600"
                  : "bg-slate-400"
              }`}
            />
          </span>
          <span className="hidden sm:inline text-[11px] font-semibold">
            {isBackendOnline === true ? "FastAPI Online" : isBackendOnline === false ? "FastAPI Offline" : "Checking..."}
          </span>
        </div>

        <Link
          href="/alerts"
          aria-label={`View notifications (${unackAlertsCount} unacknowledged alerts)`}
          className="relative rounded-lg p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 border border-transparent hover:border-[#e6e7e3]"
        >
          <MaterialIcon name="notifications" className="h-4 w-4" aria-hidden="true" />
          {unackAlertsCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-amber-600 px-1 text-[9px] font-bold text-white tabular-nums border border-white">
              {unackAlertsCount}
            </span>
          )}
        </Link>

        <div className="relative">
          <button
            type="button"
            onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
            aria-label="User account menu"
            className="flex items-center gap-2 rounded-lg p-1 text-slate-700 hover:bg-[#f8f8f6] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 cursor-pointer"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-900 text-[11px] font-bold text-emerald-100">
              SL
            </div>
            <div className="hidden xl:flex flex-col text-left leading-none">
              <span className="text-xs font-semibold text-slate-900">Sarah Lin</span>
              <span className="text-[10px] text-slate-500">Ops Manager</span>
            </div>
          </button>

          {profileDropdownOpen && (
            <div
              className="absolute right-0 mt-1 w-48 rounded-lg border border-[#e6e7e3] bg-white py-1 shadow-md z-50 text-xs"
              onMouseLeave={() => setProfileDropdownOpen(false)}
            >
              <div className="px-3 py-2 border-b border-[#eeefec]">
                <p className="font-semibold text-slate-900">Sarah Lin</p>
                <p className="text-[10px] text-slate-500">ops@supermarket104.internal</p>
              </div>
              <Link
                href="/settings"
                onClick={() => setProfileDropdownOpen(false)}
                className="block px-3 py-1.5 text-slate-700 hover:bg-[#f8f8f6]"
              >
                Store Settings
              </Link>
              <Link
                href="/video-analytics"
                onClick={() => setProfileDropdownOpen(false)}
                className="block px-3 py-1.5 text-slate-700 hover:bg-[#f8f8f6]"
              >
                Camera Pipelines
              </Link>
              <div className="border-t border-[#eeefec] my-1" />
              <div className="px-3 py-1 text-[10px] text-slate-400 flex items-center gap-1">
                <MaterialIcon name="shield" className="h-3 w-3 text-emerald-700" aria-hidden="true" />
                <span>Operator Privileges</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
