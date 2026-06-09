/**
 * Theme Management — Dark/Light mode with system preference detection
 */

export type Theme = "light" | "dark" | "system";

const THEME_KEY = "54link_theme";

export function getStoredTheme(): Theme {
  if (typeof localStorage === "undefined") return "system";
  return (localStorage.getItem(THEME_KEY) as Theme) || "system";
}

export function setTheme(theme: Theme) {
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(THEME_KEY, theme);
  }
  applyTheme(theme);
}

export function getEffectiveTheme(theme: Theme): "light" | "dark" {
  if (theme === "system") {
    return typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return theme;
}

export function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  const effective = getEffectiveTheme(theme);
  document.documentElement.classList.remove("light", "dark");
  document.documentElement.classList.add(effective);
  document.documentElement.setAttribute("data-theme", effective);
}

// Initialize on load
if (typeof window !== "undefined") {
  applyTheme(getStoredTheme());

  // Listen for system theme changes
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      if (getStoredTheme() === "system") {
        applyTheme("system");
      }
    });
}
