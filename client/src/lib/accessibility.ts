/**
 * Accessibility Helpers — WCAG 2.1 AA compliance utilities
 */

export function announceToScreenReader(
  message: string,
  priority: "polite" | "assertive" = "polite"
) {
  const el = document.createElement("div");
  el.setAttribute("aria-live", priority);
  el.setAttribute("aria-atomic", "true");
  el.setAttribute("role", "status");
  el.className = "sr-only";
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => document.body.removeChild(el), 1000);
}

export function trapFocus(container: HTMLElement) {
  const focusable = container.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
  );
  if (focusable.length === 0) return () => {};

  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  const handler = (e: KeyboardEvent) => {
    if (e.key !== "Tab") return;
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };

  container.addEventListener("keydown", handler);
  first.focus();
  return () => container.removeEventListener("keydown", handler);
}

export function getContrastRatio(fg: string, bg: string): number {
  const fgLum = relativeLuminance(parseColor(fg));
  const bgLum = relativeLuminance(parseColor(bg));
  const lighter = Math.max(fgLum, bgLum);
  const darker = Math.min(fgLum, bgLum);
  return (lighter + 0.05) / (darker + 0.05);
}

export function meetsContrastAA(
  fg: string,
  bg: string,
  isLargeText = false
): boolean {
  const ratio = getContrastRatio(fg, bg);
  return isLargeText ? ratio >= 3 : ratio >= 4.5;
}

function parseColor(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [
    parseInt(h.substring(0, 2), 16),
    parseInt(h.substring(2, 4), 16),
    parseInt(h.substring(4, 6), 16),
  ];
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const [rs, gs, bs] = [r, g, b].map(c => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

export function setupKeyboardNavigation() {
  if (typeof document === "undefined") return;

  document.addEventListener("keydown", e => {
    // Skip link on Tab
    if (e.key === "Tab" && !e.shiftKey) {
      const skipLink = document.getElementById("skip-to-main");
      if (skipLink && document.activeElement === document.body) {
        skipLink.focus();
      }
    }

    // Escape closes modals
    if (e.key === "Escape") {
      const modal = document.querySelector('[role="dialog"]');
      if (modal) {
        const closeBtn = modal.querySelector<HTMLElement>(
          'button[aria-label*="close"], button[aria-label*="Close"]'
        );
        if (closeBtn) closeBtn.click();
      }
    }
  });
}
