export default function LoadingSkeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className}`} />;
}

export function DashboardPageSkeleton({
  cards = 3,
  rows = 1,
}: {
  cards?: number;
  rows?: number;
}) {
  return (
    <div className="space-y-4 p-6">
      <LoadingSkeleton className="h-8 w-1/3" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {Array.from({ length: cards }, (_, i) => (
          <LoadingSkeleton key={i} className="h-24" />
        ))}
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <LoadingSkeleton key={i} className="h-64 w-full" />
      ))}
    </div>
  );
}
