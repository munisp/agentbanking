import React from "react";

export function Dialog({ children, open, onOpenChange }: { children?: React.ReactNode; open?: boolean; onOpenChange?: (o: boolean) => void }) {
  if (!open) return null;
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => onOpenChange?.(false)}>{children}</div>;
}
export function DialogTrigger({ children }: { children?: React.ReactNode; asChild?: boolean }) { return <>{children}</>; }
export function DialogContent({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <div className={`bg-white rounded-xl p-6 shadow-2xl max-w-lg w-full mx-4 ${className}`} onClick={e => e.stopPropagation()}>{children}</div>;
}
export function DialogHeader({ children }: { children?: React.ReactNode }) { return <div className="mb-4">{children}</div>; }
export function DialogTitle({ children }: { children?: React.ReactNode }) { return <h2 className="text-lg font-bold">{children}</h2>; }
export function DialogDescription({ children }: { children?: React.ReactNode }) { return <p className="text-sm text-gray-500">{children}</p>; }
export function DialogFooter({ children }: { children?: React.ReactNode }) { return <div className="mt-4 flex justify-end gap-2">{children}</div>; }
export function DialogClose({ children }: { children?: React.ReactNode }) { return <>{children}</>; }
