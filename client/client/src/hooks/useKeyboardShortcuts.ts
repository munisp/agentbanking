/**
 * Sprint 52 — Keyboard Shortcuts
 * F16: Ctrl+K search, Esc close modals, keyboard navigation
 */
import { useEffect, useCallback } from "react";

interface ShortcutMap {
  [key: string]: () => void;
}

/**
 * Hook to register keyboard shortcuts.
 * Keys format: "ctrl+k", "escape", "ctrl+shift+e"
 */
export function useKeyboardShortcuts(shortcuts: ShortcutMap) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const parts: string[] = [];
      if (e.ctrlKey || e.metaKey) parts.push("ctrl");
      if (e.shiftKey) parts.push("shift");
      if (e.altKey) parts.push("alt");
      parts.push(e.key.toLowerCase());
      const combo = parts.join("+");

      const handler = shortcuts[combo];
      if (handler) {
        e.preventDefault();
        e.stopPropagation();
        handler();
      }
    },
    [shortcuts]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}

/**
 * Common shortcuts for dashboard pages
 */
export function useDashboardShortcuts({
  onSearch,
  onNew,
  onExport,
  onRefresh,
}: {
  onSearch?: () => void;
  onNew?: () => void;
  onExport?: () => void;
  onRefresh?: () => void;
}) {
  useKeyboardShortcuts({
    ...(onSearch ? { "ctrl+k": onSearch } : {}),
    ...(onNew ? { "ctrl+n": onNew } : {}),
    ...(onExport ? { "ctrl+shift+e": onExport } : {}),
    ...(onRefresh ? { "ctrl+r": onRefresh } : {}),
  });
}

export default useKeyboardShortcuts;
