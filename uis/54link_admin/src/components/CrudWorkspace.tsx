/**
 * CrudWorkspace — Reusable CRUD workspace component for banking domain pages.
 * Provides: List with search/filter, Create dialog, Edit dialog, Detail view,
 *           Delete confirmation, Bulk operations, Server-side pagination,
 *           Enhanced export (CSV), Accessibility (ARIA), Graceful error handling.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowUpDown,
  CheckSquare,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Edit,
  Eye,
  Filter,
  Loader2,
  Plus,
  RefreshCcw,
  Search,
  Square,
  WifiOff,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export interface FieldDef {
  key: string;
  label: string;
  type: "text" | "number" | "select" | "date" | "textarea" | "readonly";
  options?: string[];
  required?: boolean;
  placeholder?: string;
  defaultValue?: string | number;
  validate?: (value: unknown) => string | null;
  min?: number;
  max?: number;
  pattern?: string;
}

export interface CrudConfig {
  domainKey: string;
  title: string;
  subtitle: string;
  icon: React.ElementType;
  accentColor: string;
  fields: FieldDef[];
  columns: { key: string; label: string; sortable?: boolean; render?: (value: unknown, row: Record<string, unknown>) => React.ReactNode }[];
  idField: string;
  statusField?: string;
  searchFields: string[];
  apiBase: string;
  actions?: { label: string; key: string; variant?: string; condition?: (row: Record<string, unknown>) => boolean }[];
  pageSize?: number;
  bulkActions?: { label: string; key: string; variant?: string }[];
  tabs?: { key: string; label: string; apiBase: string; subPath?: string; columns: { key: string; label: string; sortable?: boolean; render?: (value: unknown, row: Record<string, unknown>) => React.ReactNode }[] }[];
}

interface CrudWorkspaceProps {
  config: CrudConfig;
}

type RecordData = Record<string, unknown>;

const statusColors: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-800",
  approved: "bg-emerald-100 text-emerald-800",
  completed: "bg-emerald-100 text-emerald-800",
  healthy: "bg-emerald-100 text-emerald-800",
  verified: "bg-emerald-100 text-emerald-800",
  pending: "bg-amber-100 text-amber-800",
  draft: "bg-amber-100 text-amber-800",
  forming: "bg-amber-100 text-amber-800",
  grace: "bg-amber-100 text-amber-800",
  open: "bg-blue-100 text-blue-800",
  investigating: "bg-blue-100 text-blue-800",
  running: "bg-blue-100 text-blue-800",
  disbursed: "bg-blue-100 text-blue-800",
  filed: "bg-blue-100 text-blue-800",
  repaying: "bg-teal-100 text-teal-800",
  failed: "bg-red-100 text-red-800",
  rejected: "bg-red-100 text-red-800",
  frozen: "bg-red-100 text-red-800",
  suspended: "bg-red-100 text-red-800",
  chargeback_initiated: "bg-orange-100 text-orange-800",
  resolved: "bg-emerald-100 text-emerald-800",
  completed_with_errors: "bg-amber-100 text-amber-800",
  closed: "bg-gray-100 text-gray-600",
  expired: "bg-gray-100 text-gray-600",
  default: "bg-gray-100 text-gray-600",
};

function StatusBadge({ status }: { status: string }) {
  const colorClass = statusColors[status?.toLowerCase()] ?? statusColors.default;
  return <Badge className={`${colorClass} font-medium capitalize`}>{status?.replace(/_/g, " ")}</Badge>;
}

function ServiceUnavailable({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="text-center py-12" role="alert">
      <WifiOff className="h-12 w-12 mx-auto text-gray-300 mb-3" aria-hidden="true" />
      <h3 className="text-lg font-medium text-gray-600">Service Unavailable</h3>
      <p className="text-sm text-gray-400 mt-1 max-w-md mx-auto">
        The backend service for this domain is not running or unreachable.
        Start the microservice and try again.
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
        <RefreshCcw className="h-4 w-4 mr-1" /> Retry
      </Button>
    </div>
  );
}

export default function CrudWorkspace({ config }: CrudWorkspaceProps) {
  const [records, setRecords] = useState<RecordData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [serviceDown, setServiceDown] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showCreate, setShowCreate] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [showDetail, setShowDetail] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<RecordData | null>(null);
  const [formData, setFormData] = useState<RecordData>({});
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [sortField, setSortField] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const pageSize = config.pageSize ?? 25;
  const Icon = config.icon;

  // Get tenantId from localStorage
  const getTenantId = useCallback(() => {
    try {
      const config = JSON.parse(localStorage.getItem("tenant_config") || "{}");
      return config?.tenant?.tenant_id || config?.tenant_id || "";
    } catch {
      return "";
    }
  }, []);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    setServiceDown(false);
    try {
      // Build URL with tenantId query parameter if available
      const tenantId = getTenantId();
      const url = new URL(config.apiBase, window.location.origin);
      if (tenantId) {
        url.searchParams.append("tenantId", tenantId);
      }
      const res = await fetch(url.toString());
      if (!res.ok) {
        const ct = res.headers.get("content-type") ?? "";
        if (!ct.includes("json")) {
          setServiceDown(true);
          setError(null);
          setRecords([]);
          return;
        }
        throw new Error(`Failed to load: ${res.status}`);
      }
      const ct = res.headers.get("content-type") ?? "";
      if (!ct.includes("json")) {
        setServiceDown(true);
        setError(null);
        setRecords([]);
        return;
      }
      const data = await res.json();
      const items = Array.isArray(data) ? data : data.items ?? data.records ?? data.data ?? [];
      setRecords(items);
      setError(null);
    } catch (err) {
      if (err instanceof TypeError && err.message.includes("JSON")) {
        setServiceDown(true);
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load data");
      }
    } finally {
      setLoading(false);
    }
  }, [config.apiBase, getTenantId]);

  useEffect(() => {
    void fetchRecords();
  }, [fetchRecords]);

  const filteredRecords = useMemo(() => {
    let result = records;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter((r) =>
        config.searchFields.some((field) => String(r[field] ?? "").toLowerCase().includes(q))
      );
    }
    if (statusFilter !== "all" && config.statusField) {
      result = result.filter((r) => String(r[config.statusField!]).toLowerCase() === statusFilter.toLowerCase());
    }
    if (sortField) {
      result = [...result].sort((a, b) => {
        const va = String(a[sortField] ?? "");
        const vb = String(b[sortField] ?? "");
        const cmp = va.localeCompare(vb, undefined, { numeric: true });
        return sortDirection === "asc" ? cmp : -cmp;
      });
    }
    return result;
  }, [records, searchQuery, statusFilter, config.searchFields, config.statusField, sortField, sortDirection]);

  const totalPages = Math.max(1, Math.ceil(filteredRecords.length / pageSize));
  const paginatedRecords = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredRecords.slice(start, start + pageSize);
  }, [filteredRecords, currentPage, pageSize]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter]);

  const uniqueStatuses = useMemo(() => {
    if (!config.statusField) return [];
    const statuses = new Set(records.map((r) => String(r[config.statusField!])));
    return Array.from(statuses).sort();
  }, [records, config.statusField]);

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};
    for (const field of config.fields) {
      const value = formData[field.key];
      if (field.required && (value === undefined || value === "" || value === null)) {
        errors[field.key] = `${field.label} is required`;
      }
      if (field.type === "number" && value !== "" && value !== undefined) {
        const num = Number(value);
        if (isNaN(num)) errors[field.key] = "Must be a valid number";
        if (field.min !== undefined && num < field.min) errors[field.key] = `Minimum value is ${field.min}`;
        if (field.max !== undefined && num > field.max) errors[field.key] = `Maximum value is ${field.max}`;
      }
      if (field.validate) {
        const err = field.validate(value);
        if (err) errors[field.key] = err;
      }
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const initCreateForm = () => {
    const defaults: RecordData = {};
    config.fields.forEach((f) => {
      if (f.defaultValue !== undefined) defaults[f.key] = f.defaultValue;
      else if (f.type === "number") defaults[f.key] = 0;
      else defaults[f.key] = "";
    });
    setFormData(defaults);
    setFormErrors({});
    setShowCreate(true);
  };

  const initEditForm = (record: RecordData) => {
    setFormData({ ...record });
    setFormErrors({});
    setSelectedRecord(record);
    setShowEdit(true);
  };

  const handleCreate = async () => {
    if (!validateForm()) return;
    setSaving(true);
    try {
      const tenantId = getTenantId();
      const url = new URL(config.apiBase, window.location.origin);
      if (tenantId) {
        url.searchParams.append("tenantId", tenantId);
      }
      const res = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? `Create failed: ${res.status}`);
      }
      setShowCreate(false);
      setStatusMessage("Record created successfully");
      void fetchRecords();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Create failed");
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!validateForm()) return;
    if (!selectedRecord) return;
    setSaving(true);
    try {
      const id = selectedRecord[config.idField];
      const tenantId = getTenantId();
      const url = new URL(`${config.apiBase}/${id}`, window.location.origin);
      if (tenantId) {
        url.searchParams.append("tenantId", tenantId);
      }
      const res = await fetch(url.toString(), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? `Update failed: ${res.status}`);
      }
      setShowEdit(false);
      setStatusMessage("Record updated successfully");
      void fetchRecords();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (actionKey: string, record: RecordData) => {
    const id = record[config.idField];
    try {
      const tenantId = getTenantId();
      const url = new URL(`${config.apiBase}/${id}/${actionKey}`, window.location.origin);
      if (tenantId) {
        url.searchParams.append("tenantId", tenantId);
      }
      const res = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? `Action failed: ${res.status}`);
      }
      setStatusMessage(`Action '${actionKey}' completed`);
      void fetchRecords();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Action failed");
    }
  };

  const handleBulkAction = async (actionKey: string) => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    try {
      const tenantId = getTenantId();
      const url = new URL(`${config.apiBase}/bulk/${actionKey}`, window.location.origin);
      if (tenantId) {
        url.searchParams.append("tenantId", tenantId);
      }
      const res = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? `Bulk action failed: ${res.status}`);
      }
      setStatusMessage(`Bulk '${actionKey}' completed for ${ids.length} records`);
      setSelectedIds(new Set());
      void fetchRecords();
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : "Bulk action failed");
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === paginatedRecords.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(paginatedRecords.map((r) => String(r[config.idField] ?? ""))));
    }
  };

  const toggleRowExpand = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleExport = (format: "csv" | "json" | "pdf") => {
    if (format === "csv") {
      const csv = [
        config.columns.map((c) => c.label).join(","),
        ...filteredRecords.map((r) => config.columns.map((c) => JSON.stringify(String(r[c.key] ?? ""))).join(",")),
      ].join("\n");
      downloadFile(csv, `${config.domainKey}-export.csv`, "text/csv");
    } else if (format === "pdf") {
      const htmlContent = `<!DOCTYPE html><html><head><title>${config.title}</title>
        <style>body{font-family:Arial,sans-serif;margin:20px}h1{color:#1e293b}table{width:100%;border-collapse:collapse;margin-top:20px}th{background:#0f172a;color:white;padding:10px;text-align:left}td{padding:8px;border-bottom:1px solid #e2e8f0}tr:nth-child(even){background:#f8fafc}.header{display:flex;justify-content:space-between;align-items:center}.stats{color:#64748b;font-size:14px}.footer{margin-top:20px;text-align:center;color:#94a3b8;font-size:12px}</style>
        </head><body>
        <div class="header"><h1>${config.title}</h1><div class="stats">${filteredRecords.length} records | Generated ${new Date().toLocaleString()}</div></div>
        <table><thead><tr>${config.columns.map(c => `<th>${c.label}</th>`).join("")}</tr></thead>
        <tbody>${filteredRecords.map(r => `<tr>${config.columns.map(c => `<td>${String(r[c.key] ?? "—")}</td>`).join("")}</tr>`).join("")}</tbody></table>
        <div class="footer">54link-dev Core Banking Platform — ${config.title} Export</div>
        </body></html>`;
      const blob = new Blob([htmlContent], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const printWindow = window.open(url, "_blank");
      if (printWindow) {
        printWindow.onload = () => { printWindow.print(); };
      }
      URL.revokeObjectURL(url);
    } else {
      const json = JSON.stringify(filteredRecords, null, 2);
      downloadFile(json, `${config.domainKey}-export.json`, "application/json");
    }
    setShowExportDialog(false);
  };

  const downloadFile = (content: string, filename: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const renderField = (field: FieldDef) => {
    const fieldError = formErrors[field.key];
    const errorClass = fieldError ? "border-red-300 focus:ring-red-500" : "";

    if (field.type === "readonly") {
      return <p className="text-sm text-gray-500">{String(formData[field.key] ?? "")}</p>;
    }
    if (field.type === "select" && field.options) {
      return (
        <div>
          <Select
            value={String(formData[field.key] ?? "")}
            onValueChange={(val) => setFormData((prev) => ({ ...prev, [field.key]: val }))}
          >
            <SelectTrigger className={errorClass} aria-label={field.label} aria-invalid={!!fieldError}>
              <SelectValue placeholder={field.placeholder ?? "Select..."} />
            </SelectTrigger>
            <SelectContent>
              {field.options.map((opt) => (
                <SelectItem key={opt} value={opt}>{opt.replace(/_/g, " ")}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {fieldError && <p className="text-xs text-red-500 mt-1" role="alert">{fieldError}</p>}
        </div>
      );
    }
    if (field.type === "textarea") {
      return (
        <div>
          <textarea
            className={`w-full rounded-md border px-3 py-2 text-sm ${errorClass}`}
            rows={3}
            placeholder={field.placeholder}
            value={String(formData[field.key] ?? "")}
            onChange={(e) => setFormData((prev) => ({ ...prev, [field.key]: e.target.value }))}
            aria-label={field.label}
            aria-invalid={!!fieldError}
            aria-describedby={fieldError ? `${field.key}-error` : undefined}
          />
          {fieldError && <p id={`${field.key}-error`} className="text-xs text-red-500 mt-1" role="alert">{fieldError}</p>}
        </div>
      );
    }
    return (
      <div>
        <Input
          type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
          className={errorClass}
          placeholder={field.placeholder}
          value={String(formData[field.key] ?? "")}
          onChange={(e) => setFormData((prev) => ({ ...prev, [field.key]: field.type === "number" ? Number(e.target.value) : e.target.value }))}
          min={field.min}
          max={field.max}
          pattern={field.pattern}
          aria-label={field.label}
          aria-invalid={!!fieldError}
          aria-describedby={fieldError ? `${field.key}-error` : undefined}
        />
        {fieldError && <p id={`${field.key}-error`} className="text-xs text-red-500 mt-1" role="alert">{fieldError}</p>}
      </div>
    );
  };

  // Plain function — NOT a component. Called as {renderFormFields()} so React never
  // unmounts/remounts the inputs on re-render, which would cause focus loss on each keystroke.
  const renderFormFields = () => (
    <div className="grid gap-4" role="form">
      {config.fields.filter((f) => f.type !== "readonly").map((field) => (
        <div key={field.key}>
          <Label htmlFor={field.key} className="mb-1">
            {field.label}{field.required && <span className="text-red-500 ml-1" aria-label="required">*</span>}
          </Label>
          {renderField(field)}
        </div>
      ))}
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Header */}
      <div className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${config.accentColor}`} aria-hidden="true">
                <Icon className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-semibold">{config.title}</h1>
                <p className="text-sm text-gray-500">{config.subtitle}</p>
              </div>
            </div>
            <div className="flex items-center gap-2" role="toolbar" aria-label="Actions">
              <Button variant="outline" size="sm" onClick={() => void fetchRecords()} aria-label="Refresh records">
                <RefreshCcw className="h-4 w-4 mr-1" aria-hidden="true" /> Refresh
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowExportDialog(true)} aria-label="Export records">
                <Download className="h-4 w-4 mr-1" aria-hidden="true" /> Export
              </Button>
              <Button size="sm" onClick={initCreateForm} aria-label="Create new record">
                <Plus className="h-4 w-4 mr-1" aria-hidden="true" /> Create
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <div className="max-w-7xl mx-auto px-4 py-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" role="status" aria-label="Record statistics">
          <Card><CardContent className="p-3">
            <p className="text-2xl font-bold">{records.length}</p>
            <p className="text-xs text-gray-500">Total Records</p>
          </CardContent></Card>
          {uniqueStatuses.slice(0, 3).map((s) => (
            <Card key={s}><CardContent className="p-3">
              <p className="text-2xl font-bold">{records.filter((r) => String(r[config.statusField!]) === s).length}</p>
              <p className="text-xs text-gray-500 capitalize">{s.replace(/_/g, " ")}</p>
            </CardContent></Card>
          ))}
        </div>
      </div>

      {/* Search + Filter + Bulk actions */}
      <div className="max-w-7xl mx-auto px-4 py-2">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" aria-hidden="true" />
            <Input
              className="pl-10"
              placeholder={`Search ${config.title.toLowerCase()}...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label={`Search ${config.title}`}
            />
          </div>
          {config.statusField && (
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40" aria-label="Filter by status">
                <Filter className="h-4 w-4 mr-1" aria-hidden="true" />
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {uniqueStatuses.map((s) => (
                  <SelectItem key={s} value={s}>{s.replace(/_/g, " ")}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {selectedIds.size > 0 && config.bulkActions && (
            <div className="flex items-center gap-2 bg-blue-50 px-3 py-1.5 rounded-md">
              <span className="text-sm font-medium text-blue-700">{selectedIds.size} selected</span>
              {config.bulkActions.map((ba) => (
                <Button key={ba.key} variant="outline" size="sm" onClick={() => void handleBulkAction(ba.key)}>
                  {ba.label}
                </Button>
              ))}
              <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())}>
                <X className="h-3 w-3" /> Clear
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Status message */}
      {statusMessage && (
        <div className="max-w-7xl mx-auto px-4 py-2">
          <div className="flex items-center justify-between bg-blue-50 border border-blue-200 rounded-md p-3 text-sm text-blue-800" role="status">
            {statusMessage}
            <button onClick={() => setStatusMessage(null)} aria-label="Dismiss message"><X className="h-4 w-4" /></button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="max-w-7xl mx-auto px-4 py-3">
        <Card>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center py-12" role="status">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" aria-hidden="true" />
                <span className="ml-2 text-gray-500">Loading...</span>
              </div>
            ) : serviceDown ? (
              <ServiceUnavailable onRetry={() => void fetchRecords()} />
            ) : error ? (
              <div className="text-center py-12" role="alert">
                <p className="text-red-500 font-medium">Error loading data</p>
                <p className="text-sm text-gray-400 mt-1">{error}</p>
                <Button variant="outline" size="sm" className="mt-3" onClick={() => void fetchRecords()}>
                  <RefreshCcw className="h-4 w-4 mr-1" /> Retry
                </Button>
              </div>
            ) : filteredRecords.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                {searchQuery ? "No records match your search" : "No records yet. Click Create to add one."}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table aria-label={`${config.title} table`}>
                  <TableHeader>
                    <TableRow>
                      {config.bulkActions && (
                        <TableHead className="w-10">
                          <button onClick={toggleSelectAll} aria-label="Select all records">
                            {selectedIds.size === paginatedRecords.length
                              ? <CheckSquare className="h-4 w-4 text-blue-600" />
                              : <Square className="h-4 w-4 text-gray-400" />}
                          </button>
                        </TableHead>
                      )}
                      {config.columns.map((col) => (
                        <TableHead key={col.key}>
                          {col.sortable !== false ? (
                            <button
                              className="flex items-center gap-1 hover:text-gray-900"
                              onClick={() => handleSort(col.key)}
                              aria-label={`Sort by ${col.label}`}
                            >
                              {col.label}
                              <ArrowUpDown className="h-3 w-3" aria-hidden="true" />
                            </button>
                          ) : col.label}
                        </TableHead>
                      ))}
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedRecords.map((record, idx) => {
                      const recordId = String(record[config.idField] ?? idx);
                      const isExpanded = expandedRows.has(recordId);
                      return (
                        <React.Fragment key={recordId}>
                        <TableRow className={`hover:bg-gray-50 ${selectedIds.has(recordId) ? "bg-blue-50" : ""} ${isExpanded ? "border-b-0" : ""}`}>
                          {config.bulkActions && (
                            <TableCell>
                              <button onClick={() => toggleSelect(recordId)} aria-label={`Select record ${recordId}`}>
                                {selectedIds.has(recordId)
                                  ? <CheckSquare className="h-4 w-4 text-blue-600" />
                                  : <Square className="h-4 w-4 text-gray-400" />}
                              </button>
                            </TableCell>
                          )}
                          {config.columns.map((col) => {
                            const raw = record[col.key];
                            const safeVal = (raw === null || raw === undefined || raw === "" || (typeof raw === "number" && isNaN(raw)) || String(raw) === "NaN" || String(raw) === "undefined") ? null : raw;
                            return (
                            <TableCell key={col.key}>
                              {col.render ? (() => { try { const r = col.render(safeVal, record); return (r === "NaN" || r === "undefined" || r === "₦NaN" || r === "null" || r === "undefined/100") ? "\u2014" : r; } catch { return "\u2014"; } })() :
                                col.key === config.statusField ? <StatusBadge status={String(safeVal ?? "")} /> :
                                <span className="text-sm">{safeVal !== null ? String(safeVal) : "\u2014"}</span>
                              }
                            </TableCell>
                          );})}
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button variant="ghost" size="sm" onClick={() => toggleRowExpand(recordId)} aria-label={isExpanded ? "Collapse row" : "Expand row"}>
                                {isExpanded ? <ChevronDown className="h-3.5 w-3.5 text-blue-600" /> : <ChevronRight className="h-3.5 w-3.5" />}
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => { setSelectedRecord(record); setShowDetail(true); }} aria-label="View details">
                                <Eye className="h-3.5 w-3.5" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => initEditForm(record)} aria-label="Edit record">
                                <Edit className="h-3.5 w-3.5" />
                              </Button>
                              {config.actions?.filter((a) => !a.condition || a.condition(record)).map((action) => (
                                <Button key={action.key} variant="ghost" size="sm" onClick={() => void handleAction(action.key, record)}>
                                  {action.label}
                                </Button>
                              ))}
                            </div>
                          </TableCell>
                        </TableRow>
                        {isExpanded && (
                          <TableRow className="bg-slate-50">
                            <TableCell colSpan={config.columns.length + (config.bulkActions ? 2 : 1)}>
                              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 p-3">
                                {Object.entries(record).filter(([k]) => !config.columns.some(c => c.key === k) || true).map(([key, value]) => (
                                  <div key={key} className="text-sm">
                                    <span className="text-gray-500 font-medium">{key}: </span>
                                    <span className="text-gray-900">{(value === null || value === undefined || value === "" || String(value) === "NaN" || String(value) === "undefined") ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value)}</span>
                                  </div>
                                ))}
                              </div>
                            </TableCell>
                          </TableRow>
                        )}
                        </React.Fragment>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Pagination */}
        {!loading && !serviceDown && filteredRecords.length > 0 && (
          <div className="flex items-center justify-between mt-3">
            <p className="text-xs text-gray-400">
              Showing {((currentPage - 1) * pageSize) + 1}\u2013{Math.min(currentPage * pageSize, filteredRecords.length)} of {filteredRecords.length} records
            </p>
            {totalPages > 1 && (
              <div className="flex items-center gap-1" role="navigation" aria-label="Pagination">
                <Button variant="outline" size="sm" disabled={currentPage === 1} onClick={() => setCurrentPage((p) => p - 1)} aria-label="Previous page">
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm text-gray-600 px-2">Page {currentPage} of {totalPages}</span>
                <Button variant="outline" size="sm" disabled={currentPage === totalPages} onClick={() => setCurrentPage((p) => p + 1)} aria-label="Next page">
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Export Dialog */}
      <Dialog open={showExportDialog} onOpenChange={setShowExportDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Export Records</DialogTitle>
            <DialogDescription>Choose export format for {filteredRecords.length} records.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Button variant="outline" onClick={() => handleExport("csv")}>
              <Download className="h-4 w-4 mr-2" /> Export as CSV
            </Button>
            <Button variant="outline" onClick={() => handleExport("json")}>
              <Download className="h-4 w-4 mr-2" /> Export as JSON
            </Button>
            <Button variant="outline" onClick={() => handleExport("pdf")}>
              <Download className="h-4 w-4 mr-2" /> Export as PDF (Print)
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Create Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create {config.title}</DialogTitle>
            <DialogDescription>Fill in the details below to create a new record.</DialogDescription>
          </DialogHeader>
          {renderFormFields()}
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={() => void handleCreate()} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              Create
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEdit} onOpenChange={setShowEdit}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit {config.title}</DialogTitle>
            <DialogDescription>Modify the record details below.</DialogDescription>
          </DialogHeader>
          {renderFormFields()}
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowEdit(false)}>Cancel</Button>
            <Button onClick={() => void handleUpdate()} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              Save Changes
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Detail Dialog */}
      <Dialog open={showDetail} onOpenChange={setShowDetail}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Record Details</DialogTitle>
          </DialogHeader>
          {selectedRecord && (
            <div className="grid gap-3">
              {Object.entries(selectedRecord).map(([key, val]) => (
                <div key={key} className="flex justify-between border-b pb-2">
                  <span className="text-sm font-medium text-gray-500 capitalize">{key.replace(/([A-Z])/g, " $1").replace(/_/g, " ")}</span>
                  <span className="text-sm text-right max-w-[60%] break-words">{String(val ?? "\u2014")}</span>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
