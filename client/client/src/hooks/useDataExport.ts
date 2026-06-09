/**
 * useDataExport — Reusable hook for CSV and PDF data export
 *
 * Usage:
 *   const { exportCSV, exportPDF, exporting } = useDataExport();
 *   exportCSV(data, columns, "transactions-export");
 */
import { useState, useCallback } from "react";

interface Column {
  key: string;
  label: string;
  format?: (value: unknown) => string;
}

export function useDataExport() {
  const [exporting, setExporting] = useState(false);

  const exportCSV = useCallback(
    (data: Record<string, unknown>[], columns: Column[], filename: string) => {
      setExporting(true);
      try {
        const header = columns.map(c => `"${c.label}"`).join(",");
        const rows = data.map(row =>
          columns
            .map(c => {
              const val = row[c.key];
              const formatted = c.format ? c.format(val) : String(val ?? "");
              return `"${formatted.replace(/"/g, '""')}"`;
            })
            .join(",")
        );
        const csv = [header, ...rows].join("\n");
        const blob = new Blob(["\uFEFF" + csv], {
          type: "text/csv;charset=utf-8;",
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${filename}-${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(url);
      } finally {
        setExporting(false);
      }
    },
    []
  );

  const exportJSON = useCallback(
    (data: Record<string, unknown>[], filename: string) => {
      setExporting(true);
      try {
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${filename}-${new Date().toISOString().slice(0, 10)}.json`;
        link.click();
        URL.revokeObjectURL(url);
      } finally {
        setExporting(false);
      }
    },
    []
  );

  const printPage = useCallback((title?: string) => {
    if (title) document.title = title;
    window.print();
  }, []);

  return { exportCSV, exportJSON, printPage, exporting };
}

export type { Column };
