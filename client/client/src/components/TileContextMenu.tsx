/**
 * TileContextMenu — Long-press context menu for POS tiles (P1 quick-actions).
 */
import { useState, useRef, useCallback } from "react";
import { haptic } from "@/lib/haptics";

interface QuickAction {
  label: string;
  icon: string;
  action: () => void;
}

interface TileContextMenuProps {
  actions: QuickAction[];
  children: React.ReactNode;
  disabled?: boolean;
}

export function TileContextMenu({
  actions,
  children,
  disabled,
}: TileContextMenuProps) {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const touchRef = useRef({ x: 0, y: 0 });

  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (disabled) return;
      const touch = e.touches[0];
      touchRef.current = { x: touch.clientX, y: touch.clientY };
      timerRef.current = setTimeout(() => {
        haptic("tap");
        setPosition({ x: touch.clientX, y: touch.clientY });
        setVisible(true);
      }, 500);
    },
    [disabled]
  );

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    const touch = e.touches[0];
    const dx = Math.abs(touch.clientX - touchRef.current.x);
    const dy = Math.abs(touch.clientY - touchRef.current.y);
    if (dx > 10 || dy > 10) {
      if (timerRef.current) clearTimeout(timerRef.current);
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const handleAction = useCallback((action: () => void) => {
    haptic("micro");
    setVisible(false);
    action();
  }, []);

  return (
    <>
      <div
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onContextMenu={e => {
          e.preventDefault();
          if (!disabled && actions.length > 0) {
            haptic("tap");
            setPosition({ x: e.clientX, y: e.clientY });
            setVisible(true);
          }
        }}
      >
        {children}
      </div>

      {visible && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-[999]"
            onClick={() => setVisible(false)}
            onTouchStart={() => setVisible(false)}
          />
          {/* Menu */}
          <div
            className="fixed z-[1000] min-w-[180px] rounded-2xl overflow-hidden shadow-2xl"
            style={{
              left: Math.min(position.x, window.innerWidth - 200),
              top: Math.min(
                position.y,
                window.innerHeight - actions.length * 48 - 20
              ),
              background: "oklch(0.14 0.012 240)",
              border: "1px solid oklch(0.25 0.015 240)",
              backdropFilter: "blur(20px)",
              animation: "scaleIn 0.15s ease-out",
            }}
          >
            {actions.map((a, i) => (
              <button
                key={i}
                onClick={() => handleAction(a.action)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/5 active:bg-white/10"
                style={{
                  borderBottom:
                    i < actions.length - 1
                      ? "1px solid oklch(0.22 0.015 240)"
                      : "none",
                }}
              >
                <span className="text-lg">{a.icon}</span>
                <span
                  className="text-sm font-medium text-white"
                  style={{ fontFamily: "'Space Grotesk', sans-serif" }}
                >
                  {a.label}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </>
  );
}
