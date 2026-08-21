/**
 * useDataExport — client-side CSV/JSON export helpers. Builds the file in
 * memory and triggers a browser download via a Blob URL.
 */

export interface ExportColumn {
  key: string;
  label: string;
  /** Optional value formatter applied before CSV escaping. */
  format?: (value: unknown) => string;
}

function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function csvEscape(value: unknown): string {
  const s = value == null ? "" : String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function useDataExport() {
  const exportToCsv = (
    data: Record<string, unknown>[],
    columnsOrFilename: ExportColumn[] | string,
    maybeFilename?: string
  ) => {
    let columns: ExportColumn[];
    let filename: string;
    if (typeof columnsOrFilename === "string") {
      filename = columnsOrFilename;
      const keys = Array.from(new Set(data.flatMap(row => Object.keys(row ?? {}))));
      columns = keys.map(k => ({ key: k, label: k }));
    } else {
      columns = columnsOrFilename;
      filename = maybeFilename ?? "export";
    }
    const header = columns.map(c => csvEscape(c.label)).join(",");
    const rows = data.map(row =>
      columns
        .map(c => {
          const raw = row?.[c.key];
          return csvEscape(c.format ? c.format(raw) : raw);
        })
        .join(",")
    );
    download(`${filename}.csv`, [header, ...rows].join("\n"), "text/csv");
  };

  const exportToJson = (data: unknown, filename: string) => {
    download(`${filename}.json`, JSON.stringify(data, null, 2), "application/json");
  };

  return { exportToCsv, exportToJson };
}
