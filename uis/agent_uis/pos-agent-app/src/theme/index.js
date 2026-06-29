import { DefaultTheme } from "react-native-paper";

const DEFAULT_PRIMARY = "#0066FF";
const DEFAULT_SECONDARY = "#69BC5E";

export function buildTheme(primaryColor = DEFAULT_PRIMARY, secondaryColor = DEFAULT_SECONDARY) {
  return {
    ...DefaultTheme,
    colors: {
      ...DefaultTheme.colors,
      primary: primaryColor,
      secondary: secondaryColor,
      accent: "#F59E0B",
      error: "#EF4444",
      warning: "#F59E0B",
      success: "#10B981",
      background: "#F9FAFB",
      surface: "#FFFFFF",
      text: "#111827",
      textSecondary: "#6B7280",
      border: "#E5E7EB",
      disabled: "#D1D5DB",
      placeholder: "#9CA3AF",
    },
    roundness: 8,
    animation: { scale: 1.0 },
  };
}

export const theme = buildTheme();

export const spacing = {
  xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 40,
};

export const typography = {
  h1: { fontSize: 32, fontWeight: "700", lineHeight: 40 },
  h2: { fontSize: 24, fontWeight: "600", lineHeight: 32 },
  h3: { fontSize: 20, fontWeight: "600", lineHeight: 28 },
  h4: { fontSize: 18, fontWeight: "600", lineHeight: 24 },
  body1: { fontSize: 16, fontWeight: "400", lineHeight: 24 },
  body2: { fontSize: 14, fontWeight: "400", lineHeight: 20 },
  caption: { fontSize: 12, fontWeight: "400", lineHeight: 16 },
};
