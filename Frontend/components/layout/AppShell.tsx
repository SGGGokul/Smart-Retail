"use client";

import { useState } from "react";
import Sidebar from "./Sidebar";
import Topnav from "./Topnav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);

  return (
    <div className="flex min-h-screen w-full bg-[#f8f8f6] font-sans text-slate-900 antialiased">
      {/* Keyboard Accessibility Skip Link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-emerald-900 focus:px-3 focus:py-2 focus:text-xs focus:font-semibold focus:text-white focus:shadow-md focus:ring-2 focus:ring-emerald-400"
      >
        Skip to main content
      </a>

      {/* Responsive Collapsible Sidebar */}
      <Sidebar
        open={mobileSidebarOpen}
        onClose={() => setMobileSidebarOpen(false)}
        collapsed={desktopCollapsed}
        onToggleCollapse={() => setDesktopCollapsed(!desktopCollapsed)}
      />

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <Topnav onMenuClick={() => setMobileSidebarOpen(true)} />
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 p-4 sm:p-6 lg:p-7 outline-none"
        >
          <div className="mx-auto max-w-7xl w-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
