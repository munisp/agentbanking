import React from "react";

export function Select({ children, value, onValueChange }: { children: React.ReactNode; value?: string; onValueChange?: (v: string) => void }) {
  return (
    <select value={value} onChange={(e) => onValueChange?.(e.target.value)} className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
      {children}
    </select>
  );
}

export function SelectTrigger({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <>{children}</>;
}

export function SelectValue({ placeholder }: { placeholder?: string }) {
  return <>{placeholder}</>;
}

export function SelectContent({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function SelectItem({ children, value }: { children: React.ReactNode; value: string }) {
  return <option value={value}>{children}</option>;
}
