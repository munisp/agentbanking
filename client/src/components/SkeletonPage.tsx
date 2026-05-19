/**
 * SkeletonPage — Reusable skeleton loading states for data-heavy pages
 */

export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-lg border bg-card p-4 space-y-3 animate-pulse ${className}`}
    >
      <div className="h-4 bg-muted rounded w-1/3" />
      <div className="h-8 bg-muted rounded w-2/3" />
      <div className="h-3 bg-muted rounded w-1/2" />
    </div>
  );
}

export function SkeletonTable({
  rows = 5,
  cols = 4,
}: {
  rows?: number;
  cols?: number;
}) {
  return (
    <div className="rounded-lg border overflow-hidden animate-pulse">
      <div className="bg-muted/50 p-3 flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="h-4 bg-muted rounded flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="p-3 flex gap-4 border-t">
          {Array.from({ length: cols }).map((_, c) => (
            <div key={c} className="h-4 bg-muted rounded flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonStats({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-pulse">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border bg-card p-4 space-y-2">
          <div className="h-3 bg-muted rounded w-1/2" />
          <div className="h-7 bg-muted rounded w-2/3" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonChart({ height = "h-64" }: { height?: string }) {
  return (
    <div className={`rounded-lg border bg-card p-4 animate-pulse ${height}`}>
      <div className="h-4 bg-muted rounded w-1/4 mb-4" />
      <div className="h-full bg-muted/50 rounded" />
    </div>
  );
}

export function SkeletonDashboard() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2 animate-pulse">
          <div className="h-7 bg-muted rounded w-48" />
          <div className="h-4 bg-muted rounded w-72" />
        </div>
        <div className="h-9 bg-muted rounded w-24 animate-pulse" />
      </div>
      <SkeletonStats />
      <div className="grid md:grid-cols-2 gap-4">
        <SkeletonChart />
        <SkeletonChart />
      </div>
      <SkeletonTable />
    </div>
  );
}
