/**
 * AccessibilityProvider — Global accessibility enhancements
 *
 * Provides:
 * - Skip-to-content link
 * - Focus visible management
 * - Reduced motion detection
 * - Screen reader announcements
 * - Keyboard navigation indicators
 */
import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";

interface A11yContextValue {
  prefersReducedMotion: boolean;
  isKeyboardUser: boolean;
  announce: (message: string, priority?: "polite" | "assertive") => void;
}

const A11yContext = createContext<A11yContextValue>({
  prefersReducedMotion: false,
  isKeyboardUser: false,
  announce: () => {},
});

export function useA11y() {
  return useContext(A11yContext);
}

export function AccessibilityProvider({ children }: { children: ReactNode }) {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [isKeyboardUser, setIsKeyboardUser] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [announcementPriority, setAnnouncementPriority] = useState<
    "polite" | "assertive"
  >("polite");

  // Detect reduced motion preference
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) =>
      setPrefersReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  // Detect keyboard vs mouse navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Tab") {
        setIsKeyboardUser(true);
        document.body.classList.add("keyboard-user");
      }
    };
    const handleMouseDown = () => {
      setIsKeyboardUser(false);
      document.body.classList.remove("keyboard-user");
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("mousedown", handleMouseDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("mousedown", handleMouseDown);
    };
  }, []);

  // Screen reader announcement
  const announce = useCallback(
    (message: string, priority: "polite" | "assertive" = "polite") => {
      setAnnouncementPriority(priority);
      setAnnouncement("");
      // Force re-render for screen readers
      requestAnimationFrame(() => setAnnouncement(message));
    },
    []
  );

  return (
    <A11yContext.Provider
      value={{ prefersReducedMotion, isKeyboardUser, announce }}
    >
      {/* Skip to content link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[9999] focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md focus:shadow-lg focus:text-sm focus:font-medium"
        tabIndex={0}
      >
        Skip to main content
      </a>

      {/* Live region for screen reader announcements */}
      <div
        role="status"
        aria-live={announcementPriority}
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </div>

      {children}
    </A11yContext.Provider>
  );
}
