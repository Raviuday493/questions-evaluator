import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#0f172a", soft: "#334155", muted: "#64748b", faint: "#94a3b8" },
        line: { DEFAULT: "#e2e8f0", strong: "#cbd5e1" },
        canvas: "#f4f6fa",
        brand: { 50: "#f3f0ff", 100: "#e7e0ff", 500: "#6d4ee0", 600: "#5b3cc4", 700: "#4a2fa3", 900: "#251c40" },
        series: { 1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a", 4: "#eda100" },
        status: { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" },
      },
      fontFamily: { sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"] },
      boxShadow: { card: "0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06)" },
    },
  },
  plugins: [],
};

export default config;
