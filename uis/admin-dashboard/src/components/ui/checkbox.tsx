import React from "react";
export function Checkbox({ checked, onCheckedChange, disabled, className = "", id }: { checked?: boolean; onCheckedChange?: (v: boolean) => void; disabled?: boolean; className?: string; id?: string }) {
  return <input id={id} type="checkbox" checked={checked} onChange={e => onCheckedChange?.(e.target.checked)} disabled={disabled} className={`w-4 h-4 rounded border-gray-300 ${className}`} />;
}
export default Checkbox;
