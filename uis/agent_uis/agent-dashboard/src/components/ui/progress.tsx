import React from "react";

export function Progress({ value = 0, className = "" }: { value?: number; className?: string }) {
  return (
    <div className={`w-full bg-gray-200 rounded-full overflow-hidden ${className}`} style={{ height: "8px" }}>
      <div
        className="bg-blue-600 h-full rounded-full transition-all"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}
