import type { ReactNode } from "react";

interface ChartCardProps {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  footer?: ReactNode;
}

export default function ChartCard({
  title,
  description,
  action,
  children,
  className = "",
  footer,
}: ChartCardProps) {
  return (
    <section
      aria-label={title}
      className={`flex flex-col justify-between rounded-xl border border-[#e6e7e3] bg-white p-4.5 sm:p-5 transition-colors ${className}`}
    >
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 mb-3 border-b border-[#eeefec]">
          <div>
            <h2 className="font-heading text-sm sm:text-base font-bold text-slate-900 tracking-normal">
              {title}
            </h2>
            {description && (
              <p className="text-xs text-slate-500 mt-0.5 leading-normal">
                {description}
              </p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>

        <div className="w-full">{children}</div>
      </div>

      {footer && (
        <div className="mt-3.5 pt-2.5 border-t border-[#eeefec] text-xs text-slate-400">
          {footer}
        </div>
      )}
    </section>
  );
}
