import React from "react";

export function PageErrorBoundary({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export default PageErrorBoundary;
