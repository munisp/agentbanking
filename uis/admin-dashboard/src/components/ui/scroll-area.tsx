import React from "react";
export function ScrollArea({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <div className={`overflow-auto ${className}`}>{children}</div>;
}
export function ScrollBar() { return null; }
