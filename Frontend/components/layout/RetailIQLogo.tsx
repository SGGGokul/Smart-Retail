import type { FC } from "react";

interface RetailIQLogoProps {
  collapsed?: boolean;
}

export const RetailIQLogo: FC<RetailIQLogoProps> = ({ collapsed = false }) => {
  return (
    <div className="flex items-center gap-2.5 select-none">
      {/* Precision Aperture Brand Symbol */}
      <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-950 text-white shadow-2xs ring-1 ring-emerald-800/40">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-4 w-4 text-emerald-400"
          aria-hidden="true"
        >
          {/* Outer Aperture Frame */}
          <rect x="3" y="3" width="18" height="18" rx="4" className="stroke-emerald-600" />
          {/* Target Reticle */}
          <circle cx="12" cy="12" r="3" className="stroke-emerald-400 fill-emerald-500/20" />
          <path d="M12 3v3M12 18v3M3 12h3M18 12h3" className="stroke-emerald-300 stroke-[1.75]" />
        </svg>
        <span className="absolute -top-1 -right-1 flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
        </span>
      </div>

      {!collapsed && (
        <div className="flex flex-col leading-none">
          <div className="flex items-center gap-1.5">
            <span className="font-heading text-sm font-extrabold tracking-tight text-slate-900">
              Retail<span className="text-emerald-700">IQ</span>
            </span>
            <span className="rounded bg-emerald-100/70 px-1 py-0.5 text-[9px] font-bold tracking-wide text-emerald-900 uppercase">
              Vision
            </span>
          </div>
          <span className="mt-0.5 text-[10px] font-medium tracking-normal text-slate-500">
            Store Intelligence
          </span>
        </div>
      )}
    </div>
  );
};

export default RetailIQLogo;
