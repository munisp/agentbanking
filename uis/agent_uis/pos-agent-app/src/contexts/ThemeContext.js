import React, { createContext, useContext, useEffect, useState } from "react";
import { useColorScheme } from "react-native";
import { buildTheme } from "../theme";
import tenantService from "../services/tenantService";

const DEFAULT_PRIMARY = "#0066FF";
const DEFAULT_SECONDARY = "#69BC5E";

const CSS_TO_HEX = {
  red: "#FF0000", green: "#008000", blue: "#0000FF", yellow: "#FFFF00",
  orange: "#FFA500", purple: "#800080", pink: "#FFC0CB", black: "#000000",
  white: "#FFFFFF", gray: "#808080", grey: "#808080", brown: "#A52A2A",
  cyan: "#00FFFF", magenta: "#FF00FF", lime: "#00FF00", navy: "#000080",
  teal: "#008080", maroon: "#800000", olive: "#808000", coral: "#FF7F50",
  salmon: "#FA8072", gold: "#FFD700", silver: "#C0C0C0", indigo: "#4B0082",
  violet: "#EE82EE", turquoise: "#40E0D0", crimson: "#DC143C",
};

const isHex = (c) => typeof c === "string" && /^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$/.test(c);

const toHex = (c) => {
  if (isHex(c)) return c;
  if (typeof c === "string") {
    const known = CSS_TO_HEX[c.toLowerCase().trim()];
    if (known) return known;
  }
  return null;
};

const ThemeContext = createContext({});

export const ThemeProvider = ({ children }) => {
  const systemColorScheme = useColorScheme();
  const [isDarkMode, setIsDarkMode] = useState(systemColorScheme === "dark");
  const [paperTheme, setPaperTheme] = useState(buildTheme());
  const [tenantConfig, setTenantConfig] = useState(null);

  useEffect(() => {
    setIsDarkMode(systemColorScheme === "dark");
  }, [systemColorScheme]);

  useEffect(() => {
    _loadTenantColors();
  }, []);

  const _applyConfig = (config) => {
    if (!config?.branding) return;
    const primary = toHex(config.branding.primary_color) ?? DEFAULT_PRIMARY;
    const secondary = toHex(config.branding.secondary_color) ?? DEFAULT_SECONDARY;
    setPaperTheme(buildTheme(primary, secondary));
    setTenantConfig(config);
  };

  const _loadTenantColors = async () => {
    try {
      // Apply any cached config immediately for fast startup
      const cached = await tenantService.getTenantConfig();
      if (cached) _applyConfig(cached);

      // Fetch fresh config from API (skips network if already cached)
      const config = await tenantService.getTenant();
      if (config?.branding) _applyConfig(config);
    } catch (_) {
      // Silently use defaults on any error
    }
  };

  const toggleTheme = () => setIsDarkMode((prev) => !prev);

  return (
    <ThemeContext.Provider
      value={{ isDarkMode, toggleTheme, paperTheme, tenantConfig }}
    >
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within a ThemeProvider");
  return context;
};

export default ThemeContext;
