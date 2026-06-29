import React from "react";
export function Avatar({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <div className={`inline-flex items-center justify-center rounded-full bg-gray-200 overflow-hidden ${className}`}>{children}</div>;
}
export function AvatarImage({ src, alt = "" }: { src?: string; alt?: string }) {
  return src ? <img src={src} alt={alt} className="w-full h-full object-cover" /> : null;
}
export function AvatarFallback({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <span className={`text-sm font-medium text-gray-600 ${className}`}>{children}</span>;
}
