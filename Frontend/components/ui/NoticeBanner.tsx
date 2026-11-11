import type { ReactNode } from "react";
import MaterialIcon from "@/components/ui/MaterialIcon";

interface NoticeBannerProps {
  type?: "success" | "warning" | "info" | "critical";
  message: ReactNode;
  onDismiss?: () => void;
  className?: string;
}

const typeStyles = {
  success: {
    container: "border-emerald-200/90 bg-emerald-50/70 text-emerald-950",
    iconName: "check_circle",
    iconColor: "text-emerald-700",
  },
  warning: {
    container: "border-amber-200/90 bg-amber-50/70 text-amber-950",
    iconName: "warning",
    iconColor: "text-amber-700",
  },
  critical: {
    container: "border-rose-200/90 bg-rose-50/70 text-rose-950",
    iconName: "error",
    iconColor: "text-rose-700",
  },
  info: {
    container: "border-sky-200/90 bg-sky-50/70 text-sky-950",
    iconName: "info",
    iconColor: "text-sky-700",
  },
};

export default function NoticeBanner({
  type = "success",
  message,
  onDismiss,
  className = "",
}: NoticeBannerProps) {
  const config = typeStyles[type];

  return (
    <div
      role="status"
      className={`flex items-center justify-between rounded-lg border px-3.5 py-2 text-xs font-medium ${config.container} ${className}`}
    >
      <div className="flex items-center gap-2">
        <MaterialIcon
          name={config.iconName}
          className={`h-4 w-4 shrink-0 ${config.iconColor}`}
          aria-hidden="true"
        />
        <span className="leading-snug">{message}</span>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="ml-3 shrink-0 rounded p-1 opacity-70 hover:opacity-100 hover:bg-black/5 transition-opacity"
          aria-label="Dismiss notice"
        >
          <MaterialIcon name="close" className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
