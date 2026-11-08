import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
}

export default function PageHeader({
  title,
  description,
  actions,
  children,
}: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between pb-3 border-b border-[#e6e7e3]/70 mb-5">
      <div className="min-w-0 flex-1">
        <h1 className="font-heading text-xl sm:text-2xl font-extrabold tracking-tight text-slate-900 break-words leading-tight">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-xs sm:text-sm text-slate-600 max-w-3xl leading-normal">
            {description}
          </p>
        )}
      </div>

      {(actions || children) && (
        <div className="flex flex-wrap items-center gap-2 shrink-0 self-start lg:self-auto pt-0.5">
          {actions}
          {children}
        </div>
      )}
    </div>
  );
}

/**
 * Legacy demonstration notices removed for real backend integration.
 * Retained with typed props to avoid breaking unused call signatures.
 */
export function DemoTag(props?: { label?: string }) {
  void props;
  return null;
}

export function CompactDemoNotice(props?: { message?: string }) {
  void props;
  return null;
}
