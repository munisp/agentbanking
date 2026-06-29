import React from "react";

export function Badge({
  children,
  variant = "default",
  className = "",
}: {
  children: React.ReactNode;
  variant?: "default" | "outline" | "destructive" | "secondary";
  className?: string;
}) {
  const variants: Record<string, string> = {
    default: "bg-blue-100 text-blue-700",
    outline: "border border-gray-300 text-gray-700",
    destructive: "bg-red-100 text-red-700",
    secondary: "bg-gray-100 text-gray-700",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${variants[variant] ?? variants.default} ${className}`}>
      {children}
    </span>
  );
}
