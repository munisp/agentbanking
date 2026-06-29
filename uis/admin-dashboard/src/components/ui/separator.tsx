import React from "react";
export function Separator({ orientation = "horizontal", className = "" }: { orientation?: "horizontal" | "vertical"; className?: string }) {
  if (orientation === "vertical") return <div className={`inline-block w-px bg-gray-200 h-full mx-2 ${className}`} />;
  return <div className={`w-full h-px bg-gray-200 my-2 ${className}`} />;
}
export default Separator;
