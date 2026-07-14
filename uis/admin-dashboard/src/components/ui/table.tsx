import React from "react";
export function Table({ children, className = "" }: { children?: React.ReactNode; className?: string }) { return <table className={`w-full text-sm ${className}`}>{children}</table>; }
export function TableHeader({ children }: { children?: React.ReactNode }) { return <thead>{children}</thead>; }
export function TableBody({ children }: { children?: React.ReactNode }) { return <tbody>{children}</tbody>; }
export function TableFooter({ children }: { children?: React.ReactNode }) { return <tfoot>{children}</tfoot>; }
export function TableRow({ children, className = "" }: { children?: React.ReactNode; className?: string }) { return <tr className={`border-b ${className}`}>{children}</tr>; }
export function TableHead({ children, className = "" }: { children?: React.ReactNode; className?: string }) { return <th className={`text-left p-3 font-semibold text-gray-600 ${className}`}>{children}</th>; }
export function TableCell({ children, className = "", colSpan }: { children?: React.ReactNode; className?: string; colSpan?: number }) { return <td colSpan={colSpan} className={`p-3 ${className}`}>{children}</td>; }
export function TableCaption({ children }: { children?: React.ReactNode }) { return <caption className="text-sm text-gray-500">{children}</caption>; }
