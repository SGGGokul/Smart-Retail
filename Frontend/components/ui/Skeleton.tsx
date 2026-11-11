export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-slate-200/80 ${className}`}
    />
  );
}

export function CardSkeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`rounded-xl border border-[#e6e7e3] bg-white p-4.5 space-y-3 animate-pulse ${className}`}
    >
      <div className="flex justify-between items-center">
        <div className="h-3.5 w-24 bg-slate-200 rounded" />
        <div className="h-4 w-12 bg-slate-100 rounded-full" />
      </div>
      <div className="h-7 w-32 bg-slate-200 rounded" />
      <div className="h-3 w-40 bg-slate-100 rounded" />
    </div>
  );
}

export function ChartSkeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`rounded-xl border border-[#e6e7e3] bg-white p-5 space-y-4 animate-pulse ${className}`}
    >
      <div className="space-y-1.5">
        <div className="h-4 w-48 bg-slate-200 rounded" />
        <div className="h-3 w-64 bg-slate-100 rounded" />
      </div>
      <div className="h-64 w-full bg-slate-100/70 rounded-lg flex items-end p-4 gap-3">
        <div className="w-1/6 h-1/3 bg-slate-200 rounded-t" />
        <div className="w-1/6 h-2/3 bg-slate-200 rounded-t" />
        <div className="w-1/6 h-1/2 bg-slate-200 rounded-t" />
        <div className="w-1/6 h-3/4 bg-slate-200 rounded-t" />
        <div className="w-1/6 h-4/5 bg-slate-200 rounded-t" />
        <div className="w-1/6 h-2/5 bg-slate-200 rounded-t" />
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 4, className = "" }: { rows?: number; className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`rounded-xl border border-[#e6e7e3] bg-white p-4.5 space-y-3 animate-pulse ${className}`}
    >
      <div className="flex justify-between items-center pb-2.5 border-b border-[#eeefec]">
        <div className="h-4 w-36 bg-slate-200 rounded" />
        <div className="h-3 w-20 bg-slate-100 rounded" />
      </div>
      <div className="space-y-2 pt-2">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex justify-between items-center py-2 border-b border-[#eeefec]/60 last:border-0">
            <div className="h-3.5 w-28 bg-slate-200 rounded" />
            <div className="h-3.5 w-44 bg-slate-100 rounded" />
            <div className="h-3.5 w-16 bg-slate-100 rounded" />
            <div className="h-5 w-20 bg-slate-200 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default Skeleton;
