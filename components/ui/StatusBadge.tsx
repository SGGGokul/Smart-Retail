import type { ReactNode } from "react";

export type BadgeVariant = "critical" | "warning" | "success" | "info" | "neutral";

interface StatusBadgeProps {
  variant: BadgeVariant;
  children: ReactNode;
  icon?: ReactNode;
  className?: string;
  size?: "sm" | "md";
}

const variantStyles: Record<BadgeVariant, { container: string; dot: string }> = {
  critical: {
    container: "bg-rose-50 text-rose-900 border border-rose-200/90",
    dot: "bg-rose-600",
  },
  warning: {
    container: "bg-amber-50 text-amber-950 border border-amber-200/90",
    dot: "bg-amber-600",
  },
  success: {
    container: "bg-emerald-50 text-emerald-950 border border-emerald-200/90",
    dot: "bg-emerald-700",
  },
  info: {
    container: "bg-sky-50 text-sky-950 border border-sky-200/90",
    dot: "bg-sky-600",
  },
  neutral: {
    container: "bg-[#f2f3ef] text-slate-800 border border-[#e6e7e3]",
    dot: "bg-slate-400",
  },
};

export default function StatusBadge({
  variant,
  children,
  icon,
  className = "",
  size = "md",
}: StatusBadgeProps) {
  const styles = variantStyles[variant];
  const sizeClasses =
    size === "sm"
      ? "px-2 py-0.5 text-[10px]"
      : "px-2.5 py-0.5 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold leading-tight tracking-tight select-none ${sizeClasses} ${styles.container} ${className}`}
    >
      {icon ? (
        <span className="shrink-0" aria-hidden="true">
          {icon}
        </span>
      ) : (
        <span className={`h-1.5 w-1.5 rounded-full ${styles.dot}`} aria-hidden="true" />
      )}
      <span>{children}</span>
    </span>
  );
}
