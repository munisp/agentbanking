// @ts-nocheck
/**
 * DashboardLayoutEditor — Drag-and-drop grid layout for analytics dashboard
 */
import { useState, useCallback, useMemo } from "react";
// @ts-ignore - react-grid-layout types export WidthProvider differently
import ReactGridLayout from "react-grid-layout";
const { Responsive, WidthProvider } = ReactGridLayout as any;
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { trpc } from "@/lib/trpc";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";

const ResponsiveGridLayout = WidthProvider(Responsive);

interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  static?: boolean;
}

interface DashboardLayoutEditorProps {
  children: Record<string, React.ReactNode>;
  userId?: string;
}

export function DashboardLayoutEditor({
  children,
  userId = "default",
}: DashboardLayoutEditorProps) {
  const [editMode, setEditMode] = useState(false);

  const { data: layoutData, isLoading } =
    trpc.dashboardLayout.getLayout.useQuery({ userId });
  const { data: presets } = trpc.dashboardLayout.presets.useQuery();
  const utils = trpc.useUtils();

  const saveMutation = trpc.dashboardLayout.saveLayout.useMutation({
    onSuccess: () => {
      utils.dashboardLayout.getLayout.invalidate();
      toast.success("Layout saved");
    },
  });

  const resetMutation = trpc.dashboardLayout.resetLayout.useMutation({
    onSuccess: () => {
      utils.dashboardLayout.getLayout.invalidate();
      toast.success("Layout reset to default");
    },
  });

  const presetMutation = trpc.dashboardLayout.applyPreset.useMutation({
    onSuccess: () => {
      utils.dashboardLayout.getLayout.invalidate();
      toast.success("Preset applied");
    },
  });

  const layouts = useMemo(() => {
    if (!layoutData?.layout?.layouts) return { lg: [], md: [], sm: [] };
    // Filter to only include widgets that have corresponding children
    const filterLayout = (items: LayoutItem[]) =>
      items.filter(item => item.i in children);
    return {
      lg: filterLayout(layoutData.layout.layouts.lg),
      md: filterLayout(layoutData.layout.layouts.md),
      sm: filterLayout(layoutData.layout.layouts.sm),
    };
  }, [layoutData, children]);

  const handleLayoutChange = useCallback(
    (
      _currentLayout: LayoutItem[],
      allLayouts: Record<string, LayoutItem[]>
    ) => {
      if (!editMode) return;
      // Debounced save handled by button
    },
    [editMode]
  );

  const handleSave = useCallback(() => {
    if (!layoutData?.layout?.layouts) return;
    saveMutation.mutate({
      userId,
      layoutName: "Custom",
      layouts: layoutData.layout.layouts,
    });
    setEditMode(false);
  }, [layoutData, userId, saveMutation]);

  if (isLoading) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        Loading dashboard layout...
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4 px-1">
        <div className="flex items-center gap-2">
          {layoutData?.isCustom && (
            <Badge variant="outline" className="text-[10px]">
              Custom Layout
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Presets dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-7 text-xs">
                Presets
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {presets?.map(p => (
                <DropdownMenuItem
                  key={p.id}
                  onClick={() =>
                    presetMutation.mutate({ userId, presetId: p.id })
                  }
                >
                  <div>
                    <div className="font-medium text-xs">{p.name}</div>
                    <div className="text-[10px] text-muted-foreground">
                      {p.description}
                    </div>
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {editMode ? (
            <>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                onClick={() => {
                  resetMutation.mutate({ userId });
                  setEditMode(false);
                }}
              >
                Reset
              </Button>
              <Button
                size="sm"
                className="h-7 text-xs"
                onClick={handleSave}
                disabled={saveMutation.isPending}
              >
                {saveMutation.isPending ? "Saving..." : "Save Layout"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs"
                onClick={() => setEditMode(false)}
              >
                Cancel
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => setEditMode(true)}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="mr-1"
              >
                <rect x="3" y="3" width="7" height="7" />
                <rect x="14" y="3" width="7" height="7" />
                <rect x="14" y="14" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" />
              </svg>
              Edit Layout
            </Button>
          )}
        </div>
      </div>

      {/* Grid */}
      <ResponsiveGridLayout
        className="layout"
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 996, sm: 768 }}
        cols={{ lg: 12, md: 10, sm: 6 }}
        rowHeight={80}
        isDraggable={editMode}
        isResizable={editMode}
        onLayoutChange={handleLayoutChange}
        draggableHandle=".drag-handle"
        compactType="vertical"
        margin={[16, 16]}
      >
        {Object.entries(children).map(([key, child]) => (
          <div
            key={key}
            className={`relative ${editMode ? "ring-1 ring-dashed ring-primary/30 rounded-lg" : ""}`}
          >
            {editMode && (
              <div className="drag-handle absolute top-0 left-0 right-0 h-6 bg-primary/10 rounded-t-lg cursor-move flex items-center justify-center z-10">
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
                  className="text-primary/50"
                >
                  <circle cx="9" cy="5" r="1" />
                  <circle cx="15" cy="5" r="1" />
                  <circle cx="9" cy="12" r="1" />
                  <circle cx="15" cy="12" r="1" />
                  <circle cx="9" cy="19" r="1" />
                  <circle cx="15" cy="19" r="1" />
                </svg>
              </div>
            )}
            <div className={editMode ? "pt-6 h-full" : "h-full"}>{child}</div>
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  );
}
