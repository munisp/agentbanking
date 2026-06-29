import React, { createContext, useContext, useState } from "react";

const TabsContext = createContext<{ active: string; setActive: (v: string) => void }>({ active: "", setActive: () => {} });

export function Tabs({ children, defaultValue, value, onValueChange, className = "" }: {
  children: React.ReactNode;
  defaultValue?: string;
  value?: string;
  onValueChange?: (v: string) => void;
  className?: string;
}) {
  const [internal, setInternal] = useState(defaultValue ?? "");
  const active = value ?? internal;
  const setActive = (v: string) => { setInternal(v); onValueChange?.(v); };
  return (
    <TabsContext.Provider value={{ active, setActive }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`flex gap-1 border-b border-gray-200 ${className}`}>{children}</div>;
}

export function TabsTrigger({ children, value, className = "" }: { children: React.ReactNode; value: string; className?: string }) {
  const { active, setActive } = useContext(TabsContext);
  return (
    <button
      onClick={() => setActive(value)}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${active === value ? "border-blue-600 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"} ${className}`}
    >
      {children}
    </button>
  );
}

export function TabsContent({ children, value, className = "" }: { children: React.ReactNode; value: string; className?: string }) {
  const { active } = useContext(TabsContext);
  if (active !== value) return null;
  return <div className={`pt-4 ${className}`}>{children}</div>;
}
