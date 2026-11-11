"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import RetailIQLogo from "./RetailIQLogo";
import MaterialIcon from "@/components/ui/MaterialIcon";

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Store Intelligence",
    items: [
      { href: "/", label: "Overview", icon: "dashboard" },
      { href: "/video-analytics", label: "Video Analytics", icon: "videocam" },
      { href: "/customer-analytics", label: "Customer Analytics", icon: "groups" },
      { href: "/shelf-monitoring", label: "Shelf Monitoring", icon: "inventory_2" },
    ],
  },
  {
    label: "Operations & Copilot",
    items: [
      { href: "/alerts", label: "Alerts & Events", icon: "notifications_active" },
      { href: "/ai-assistant", label: "RetailIQ Copilot", icon: "smart_toy" },
      { href: "/reports", label: "Reports & Exports", icon: "analytics" },
      { href: "/settings", label: "Settings", icon: "settings" },
    ],
  },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export default function Sidebar({
  open,
  onClose,
  collapsed = false,
  onToggleCollapse,
}: SidebarProps) {
  const pathname = usePathname();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  return (
    <>
      {open && (
        <div
          aria-hidden="true"
          onClick={onClose}
          className="fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-xs transition-opacity lg:hidden"
        />
      )}

      <aside
        aria-label="Sidebar navigation"
        className={`fixed inset-y-0 left-0 z-50 flex shrink-0 flex-col border-r border-[#e6e7e3] bg-white transition-all duration-200 ease-in-out lg:static ${
          collapsed ? "lg:w-18" : "lg:w-64"
        } ${open ? "w-64 translate-x-0 shadow-lg" : "-translate-x-full lg:translate-x-0"}`}
      >
        <div
          className={`flex h-15 shrink-0 items-center border-b border-[#e6e7e3] px-4 ${
            collapsed ? "justify-center" : "justify-between"
          }`}
        >
          <Link
            href="/"
            target="_self"
            aria-label="RetailIQ dashboard"
            onClick={onClose}
            className="flex items-center gap-2 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700"
          >
            <RetailIQLogo collapsed={collapsed} />
          </Link>

          {!collapsed && onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              aria-label="Collapse sidebar"
              className="hidden lg:flex rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 cursor-pointer"
              title="Collapse sidebar"
            >
              <MaterialIcon name="left_panel_close" className="h-4 w-4" aria-hidden="true" />
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 lg:hidden cursor-pointer"
          >
            <MaterialIcon name="close" className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {collapsed && onToggleCollapse && (
          <div className="hidden lg:flex justify-center py-2 border-b border-[#eeefec]">
            <button
              type="button"
              onClick={onToggleCollapse}
              aria-label="Expand sidebar"
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 cursor-pointer"
              title="Expand sidebar"
            >
              <MaterialIcon name="left_panel_open" className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-2.5 py-4 space-y-5">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="space-y-1">
              {!collapsed && (
                <p className="px-2.5 pb-1.5 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
                  {group.label}
                </p>
              )}
              <nav aria-label={group.label} className="flex flex-col gap-0.5">
                {group.items.map(({ href, label, icon }) => {
                  const active = pathname === href;
                  return (
                    <Link
                      key={href}
                      href={href}
                      target="_self"
                      onClick={onClose}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? label : undefined}
                      aria-label={collapsed ? label : undefined}
                      className={`group relative flex items-center rounded-lg px-2.5 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700 ${
                        collapsed ? "justify-center" : "justify-between"
                      } ${
                        active
                          ? "bg-emerald-900 text-white font-semibold shadow-2xs"
                          : "text-slate-600 hover:bg-[#f2f3ef] hover:text-slate-900"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <MaterialIcon
                          name={icon}
                          className={`h-4.5 w-4.5 shrink-0 transition-colors ${
                            active
                              ? "text-emerald-300"
                              : "text-slate-400 group-hover:text-slate-700"
                          }`}
                          aria-hidden="true"
                        />
                        {!collapsed && <span className="truncate">{label}</span>}
                      </div>

                      {!collapsed && active && (
                        <MaterialIcon name="chevron_right" className="h-3.5 w-3.5 text-emerald-300 shrink-0 ml-0.5" aria-hidden="true" />
                      )}
                    </Link>
                  );
                })}
              </nav>
            </div>
          ))}
        </div>

        <div className="border-t border-[#e6e7e3] p-2.5">
          {collapsed ? (
            <div
              className="flex justify-center p-2 rounded-lg bg-[#f8f8f6] border border-[#e6e7e3]"
              title="Store #104 · FastAPI Backend Target"
            >
              <MaterialIcon name="sensors" className="h-3.5 w-3.5 text-emerald-700" aria-hidden="true" />
            </div>
          ) : (
            <div className="rounded-lg border border-[#e6e7e3] bg-[#f8f8f6] p-2.5">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                  <MaterialIcon name="storefront" className="h-3.5 w-3.5 text-emerald-700" aria-hidden="true" />
                  Store #104
                </span>
                <span className="flex items-center gap-1 text-[9px] font-bold text-emerald-900 bg-emerald-100/80 px-1.5 py-0.5 rounded-full border border-emerald-200">
                  FastAPI
                </span>
              </div>
              <p className="mt-1 text-[10px] text-slate-500 leading-tight">
                Computer-Vision Edge Target · Port 8000
              </p>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
