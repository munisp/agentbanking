import React from "react";

export function Dialog({ children, open }: { children: React.ReactNode; open?: boolean }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" />
      <div className="relative z-50">{children}</div>
    </div>
  );
}

export function DialogContent({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-xl shadow-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto ${className}`}>
      {children}
    </div>
  );
}

export function DialogHeader({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`mb-4 ${className}`}>{children}</div>;
}

export function DialogTitle({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <h2 className={`text-lg font-semibold text-gray-900 ${className}`}>{children}</h2>;
}

export function DialogFooter({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`mt-6 flex justify-end gap-3 ${className}`}>{children}</div>;
}

export function DialogTrigger({ children, asChild: _asChild }: { children: React.ReactNode; asChild?: boolean }) {
  return <>{children}</>;
}

export function DialogDescription({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <p className={`text-sm text-gray-500 ${className}`}>{children}</p>;
}

export function DialogClose({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={className}>{children}</div>;
}
