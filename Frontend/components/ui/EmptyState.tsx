import type { ReactNode } from "react";
import MaterialIcon from "@/components/ui/MaterialIcon";

interface EmptyStateProps {
  icon: string;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  children?: ReactNode;
  className?: string;
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
  children,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-[#e6e7e3] bg-white p-8 sm:p-10 text-center ${className}`}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#f2f3ef] text-slate-600 mb-3">
        <MaterialIcon name={icon} className="h-5 w-5 text-slate-600" aria-hidden="true" />
      </div>
      <h3 className="font-heading text-sm font-bold text-slate-900">{title}</h3>
      <p className="mt-1 max-w-sm text-xs text-slate-500 leading-relaxed">
        {description}
      </p>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-3.5 rounded-lg border border-[#e6e7e3] bg-[#f8f8f6] px-3.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-white hover:text-slate-900 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-700"
        >
          {action.label}
        </button>
      )}
      {children}
    </div>
  );
}
