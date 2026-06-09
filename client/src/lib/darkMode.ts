/**
 * Dark Mode — system preference detection + user override
 */
export type ThemeMode = "light" | "dark" | "system";

const STORAGE_KEY = "54link_theme";

export function getStoredTheme(): ThemeMode {
  if (typeof localStorage === "undefined") return "system";
  return (localStorage.getItem(STORAGE_KEY) as ThemeMode) || "system";
}

export function setTheme(mode: ThemeMode) {
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(STORAGE_KEY, mode);
  }
  applyTheme(mode);
}

export function applyTheme(mode: ThemeMode) {
  if (typeof document === "undefined") return;

  const root = document.documentElement;
  if (mode === "system") {
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches;
    root.classList.toggle("dark", prefersDark);
  } else {
    root.classList.toggle("dark", mode === "dark");
  }
}

export function initTheme() {
  const stored = getStoredTheme();
  applyTheme(stored);

  // Listen for system preference changes
  if (typeof window !== "undefined") {
    window
      .matchMedia("(prefers-color-scheme: dark)")
      .addEventListener("change", e => {
        if (getStoredTheme() === "system") {
          document.documentElement.classList.toggle("dark", e.matches);
        }
      });
  }
}

export function toggleTheme(): ThemeMode {
  const current = getStoredTheme();
  const next: ThemeMode =
    current === "light" ? "dark" : current === "dark" ? "system" : "light";
  setTheme(next);
  return next;
}
