"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { HourlyPoint } from "@/types";

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value?: number | string }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border border-[#e6e7e3] bg-white p-2.5 shadow-sm text-xs">
        <p className="font-bold text-slate-900">{label}:00 hrs</p>
        <p className="mt-1 flex items-center gap-1.5 font-semibold text-emerald-800 tabular-nums">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-700" />
          <span>{Number(payload[0].value).toLocaleString()} visitors</span>
        </p>
      </div>
    );
  }
  return null;
}

export default function HourlyBarChart({ data }: { data: HourlyPoint[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-68 w-full flex items-center justify-center rounded-lg border border-dashed border-[#e6e7e3] bg-[#fafaf8] text-xs text-slate-500">
        No hourly traffic telemetry available for this period.
      </div>
    );
  }
  return (
    <div className="h-68 w-full" role="img" aria-label="Hourly customer distribution chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 10, bottom: 4, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eeefec" vertical={false} />
          <XAxis
            dataKey="hour"
            tick={{ fontSize: 11, fill: "#858e9c" }}
            tickFormatter={(h: string) => `${h}:00`}
            tickLine={false}
            axisLine={{ stroke: "#e6e7e3" }}
            tickMargin={6}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#858e9c" }}
            tickLine={false}
            axisLine={false}
            width={40}
            allowDecimals={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar
            dataKey="customers"
            name="Visitors per hour"
            fill="#065f46"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
