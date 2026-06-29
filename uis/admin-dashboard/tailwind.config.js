/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Primary and secondary resolve to CSS variables set by TenantBrandingContext.
        // Fallbacks match the default tenant branding so static builds look correct.
        primary: {
          DEFAULT: "var(--tenant-primary-color, #002082)",
          50: "#E6E9F5",
          100: "#B0B8E0",
          200: "#7A86CC",
          300: "#4454B8",
          400: "#1F33A6",
          500: "var(--tenant-primary-color, #002082)",
          600: "#001A6B",
          700: "#001453",
          800: "#000E3B",
          900: "#000823",
        },
        secondary: {
          DEFAULT: "var(--tenant-secondary-color, #6CC049)",
          50: "#F1F9ED",
          100: "#D6EFCB",
          200: "#B8E4A5",
          300: "#9AD97F",
          400: "#7CCE5F",
          500: "var(--tenant-secondary-color, #6CC049)",
          600: "#5AA63C",
          700: "#4A8A31",
          800: "#3A6E26",
          900: "#2A521B",
        },
      },
    },
  },
  plugins: [],
};
