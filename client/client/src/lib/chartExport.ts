/**
 * Chart Export Utilities — PNG screenshot + CSV data export
 */

// ─── PNG Export via html2canvas approach (SVG → Canvas → PNG) ─────────────────
export async function exportChartAsPng(
  chartContainerRef: React.RefObject<HTMLDivElement | null>,
  filename: string = "chart"
): Promise<void> {
  const container = chartContainerRef.current;
  if (!container) throw new Error("Chart container ref is null");

  const svgElement = container.querySelector("svg.recharts-surface");
  if (!svgElement) throw new Error("No Recharts SVG found in container");

  const svgData = new XMLSerializer().serializeToString(svgElement);
  const svgBlob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(svgBlob);

  const img = new Image();
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D context not available");

  return new Promise((resolve, reject) => {
    img.onload = () => {
      // Use 2x for retina quality
      const scale = 2;
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      ctx.scale(scale, scale);

      // White background
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, img.width, img.height);
      ctx.drawImage(img, 0, 0);

      canvas.toBlob(blob => {
        if (!blob) {
          reject(new Error("Failed to create PNG blob"));
          return;
        }
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = `${filename}-${new Date().toISOString().slice(0, 10)}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(downloadUrl);
        URL.revokeObjectURL(url);
        resolve();
      }, "image/png");
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to load SVG as image"));
    };
    img.src = url;
  });
}

// ─── CSV Export ───────────────────────────────────────────────────────────────
export interface CsvColumn {
  key: string;
  header: string;
  formatter?: (value: unknown) => string;
}

export function exportDataAsCsv(
  data: Record<string, unknown>[],
  columns: CsvColumn[],
  filename: string = "data"
): void {
  if (!data.length) throw new Error("No data to export");

  const headers = columns.map(c => c.header);
  const rows = data.map(row =>
    columns.map(col => {
      const value = row[col.key];
      if (col.formatter) return escapeCsvField(col.formatter(value));
      if (value === null || value === undefined) return "";
      return escapeCsvField(String(value));
    })
  );

  const csvContent = [headers.join(","), ...rows.map(r => r.join(","))].join(
    "\n"
  );

  const blob = new Blob(["\uFEFF" + csvContent], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escapeCsvField(field: string): string {
  if (field.includes(",") || field.includes('"') || field.includes("\n")) {
    return `"${field.replace(/"/g, '""')}"`;
  }
  return field;
}

// ─── Chart Export Menu Component ─────────────────────────────────────────────
export type ExportFormat = "png" | "csv";

export interface ChartExportConfig {
  chartRef: React.RefObject<HTMLDivElement | null>;
  data: Record<string, unknown>[];
  columns: CsvColumn[];
  filename: string;
}
