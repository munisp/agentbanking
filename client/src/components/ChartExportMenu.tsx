/**
 * ChartExportMenu — Dropdown menu for exporting charts as PNG or CSV
 */
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  exportChartAsPng,
  exportDataAsCsv,
  type CsvColumn,
} from "@/lib/chartExport";
import { toast } from "sonner";

interface ChartExportMenuProps {
  chartRef: React.RefObject<HTMLDivElement | null>;
  data: Record<string, unknown>[];
  columns: CsvColumn[];
  filename: string;
}

export function ChartExportMenu({
  chartRef,
  data,
  columns,
  filename,
}: ChartExportMenuProps) {
  const [exporting, setExporting] = useState(false);

  const handlePngExport = async () => {
    setExporting(true);
    try {
      await exportChartAsPng(chartRef, filename);
      toast.success("Chart exported as PNG");
    } catch (err) {
      toast.error(
        `PNG export failed: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    } finally {
      setExporting(false);
    }
  };

  const handleCsvExport = () => {
    try {
      exportDataAsCsv(data, columns, filename);
      toast.success("Data exported as CSV");
    } catch (err) {
      toast.error(
        `CSV export failed: ${err instanceof Error ? err.message : "Unknown error"}`
      );
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          disabled={exporting}
          className="h-7 px-2 text-xs"
        >
          {exporting ? (
            <span className="animate-spin mr-1">&#8635;</span>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mr-1"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
          )}
          Export
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={handlePngExport}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="mr-2"
          >
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
          Export as PNG
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleCsvExport} disabled={!data.length}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="mr-2"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          Export as CSV
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * useChartExport — Hook to create a chart ref and export config
 */
export function useChartExport() {
  const chartRef = useRef<HTMLDivElement>(null);
  return { chartRef };
}
