import type { Config } from "tailwindcss";

// Palette ported from the prototype (dark-first, violet accent).
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        fg: "var(--fg)",
        "fg-muted": "var(--fg-muted)",
        "v-deep": "var(--v-deep)",
        "v-bright": "var(--v-bright)",
        "v-soft": "var(--v-soft)",
        "on-violet": "var(--fg-on-violet)",
        success: "var(--success)",
        warning: "var(--warning)",
        error: "var(--error)",
        border: "var(--border)",
      },
      borderRadius: {
        input: "10px",
        button: "10px",
        card: "14px",
        modal: "16px",
        pill: "9999px",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
