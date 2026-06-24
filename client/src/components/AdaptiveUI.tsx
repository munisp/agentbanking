/**
 * Adaptive UI Engine
 * Adjusts interface complexity based on agent proficiency level:
 * - Beginner: guided wizard with tooltips, large buttons, step-by-step
 * - Intermediate: standard UI with shortcuts visible
 * - Expert: minimal UI, keyboard shortcuts, bulk actions, voice input
 *
 * Learns from usage patterns and auto-upgrades proficiency.
 */
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

type ProficiencyLevel = "beginner" | "intermediate" | "expert";

interface AgentProfile {
  level: ProficiencyLevel;
  totalTransactions: number;
  avgTxTimeMs: number;
  preferredInput: "touch" | "keyboard" | "voice";
  shortcutsEnabled: boolean;
}

interface AdaptiveContextValue {
  profile: AgentProfile;
  updateProfile: (updates: Partial<AgentProfile>) => void;
  showGuide: boolean;
  showShortcuts: boolean;
  compactMode: boolean;
  recordTransaction: (durationMs: number) => void;
}

const defaultProfile: AgentProfile = {
  level: "beginner",
  totalTransactions: 0,
  avgTxTimeMs: 0,
  preferredInput: "touch",
  shortcutsEnabled: false,
};

const AdaptiveContext = createContext<AdaptiveContextValue>({
  profile: defaultProfile,
  updateProfile: () => {},
  showGuide: true,
  showShortcuts: false,
  compactMode: false,
  recordTransaction: () => {},
});

export function useAdaptiveUI() {
  return useContext(AdaptiveContext);
}

export function AdaptiveUIProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<AgentProfile>(() => {
    if (typeof localStorage === "undefined") return defaultProfile;
    const stored = localStorage.getItem("54link_agent_profile");
    return stored ? JSON.parse(stored) : defaultProfile;
  });

  useEffect(() => {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("54link_agent_profile", JSON.stringify(profile));
    }
  }, [profile]);

  const updateProfile = useCallback((updates: Partial<AgentProfile>) => {
    setProfile(prev => ({ ...prev, ...updates }));
  }, []);

  const recordTransaction = useCallback((durationMs: number) => {
    setProfile(prev => {
      const newTotal = prev.totalTransactions + 1;
      const newAvg = Math.round(
        (prev.avgTxTimeMs * prev.totalTransactions + durationMs) / newTotal
      );

      // Auto-upgrade based on proficiency signals
      let newLevel = prev.level;
      if (newTotal >= 500 && newAvg < 15000) {
        newLevel = "expert";
      } else if (newTotal >= 50 && newAvg < 30000) {
        newLevel = "intermediate";
      }

      return {
        ...prev,
        totalTransactions: newTotal,
        avgTxTimeMs: newAvg,
        level: newLevel,
        shortcutsEnabled: newLevel !== "beginner",
      };
    });
  }, []);

  const showGuide = profile.level === "beginner";
  const showShortcuts = profile.level !== "beginner" && profile.shortcutsEnabled;
  const compactMode = profile.level === "expert";

  return (
    <AdaptiveContext.Provider value={{ profile, updateProfile, showGuide, showShortcuts, compactMode, recordTransaction }}>
      {children}
    </AdaptiveContext.Provider>
  );
}

/**
 * Conditional render based on proficiency
 */
export function ForBeginners({ children }: { children: ReactNode }) {
  const { profile } = useAdaptiveUI();
  if (profile.level !== "beginner") return null;
  return <>{children}</>;
}

export function ForExperts({ children }: { children: ReactNode }) {
  const { profile } = useAdaptiveUI();
  if (profile.level === "beginner") return null;
  return <>{children}</>;
}

/**
 * Keyboard shortcut handler (expert mode)
 */
export function useKeyboardShortcuts(shortcuts: Record<string, () => void>) {
  const { showShortcuts } = useAdaptiveUI();

  useEffect(() => {
    if (!showShortcuts) return;

    const handler = (e: KeyboardEvent) => {
      // Ctrl+1 = Cash In, Ctrl+2 = Cash Out, etc.
      const key = `${e.ctrlKey ? "Ctrl+" : ""}${e.key}`;
      if (shortcuts[key]) {
        e.preventDefault();
        shortcuts[key]();
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [showShortcuts, shortcuts]);
}
