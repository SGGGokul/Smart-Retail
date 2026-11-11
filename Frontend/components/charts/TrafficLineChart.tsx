"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { TrafficPoint } from "@/types";

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value?: number | string }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border border-[#e6e7e3] bg-white p-2.5 shadow-sm text-xs">
        <p className="font-bold text-slate-900">{label}</p>
        <p className="mt-1 flex items-center gap-1.5 font-semibold text-emerald-800 tabular-nums">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-700" />
          <span>{Number(payload[0].value).toLocaleString()} visitors</span>
        </p>
      </div>
    );
  }
  return null;
}

export default function TrafficLineChart({ data }: { data: TrafficPoint[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-68 w-full flex items-center justify-center rounded-lg border border-dashed border-[#e6e7e3] bg-[#fafaf8] text-xs text-slate-500">
        No daily footfall telemetry available for this period.
      </div>
    );
  }
  return (
    <div className="h-68 w-full" role="img" aria-label="Customer traffic daily trend">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, bottom: 4, left: -16 }}>
          <defs>
            <linearGradient id="trafficGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#065f46" stopOpacity={0.14} />
              <stop offset="95%" stopColor="#065f46" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#eeefec" vertical={false} />
          <XAxis
            dataKey="day"
            tick={{ fontSize: 11, fill: "#858e9c" }}
            tickLine={false}
            axisLine={{ stroke: "#e6e7e3" }}
            tickMargin={6}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#858e9c" }}
            tickLine={false}
            axisLine={false}
            width={44}
            allowDecimals={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="customers"
            name="Visitors"
            stroke="#065f46"
            strokeWidth={2}
            fill="url(#trafficGradient)"
            dot={{ r: 3, fill: "#ffffff", stroke: "#065f46", strokeWidth: 2 }}
            activeDot={{ r: 5, fill: "#065f46", stroke: "#ffffff", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
