import type { Config } from "tailwindcss";

// Cisco visual identity palette (sourced from CLAUDE.md).
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cisco: {
          blue: "#049FD9",
          green: "#6EBE4A",
          yellow: "#FFCC00",
          red: "#CF2030",
        },
        surface: {
          background: "#1A1A2E",
          secondary: "#0D274D",
          DEFAULT: "#1E2A3A",
          card: "#243447",
          sidebar: "#0D1B2A",
          border: "#2D3E50",
          hover: "#1A3A5C",
          selected: "#0A4D7A",
        },
        muted: {
          DEFAULT: "#A0AEC0",
          dim: "#6B7B8D",
        },
      },
      fontFamily: {
        sans: [
          "CiscoSans",
          "Inter",
          "Open Sans",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
      fontSize: {
        metric: ["32px", { lineHeight: "1.1", letterSpacing: "-0.01em", fontWeight: "600" }],
      },
      boxShadow: {
        card: "0 2px 8px rgba(0, 0, 0, 0.3)",
      },
      maxWidth: {
        content: "1440px",
      },
    },
  },
  plugins: [],
} satisfies Config;
