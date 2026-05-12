import type { Config } from "tailwindcss";

/**
 * ClaimsFlow design tokens.
 * Deliberately NOT the default Tailwind palette. The dashboard should not
 * feel like a generic AI assistant — it's an enterprise operations tool.
 *
 * Palette: cool slate base with a single deliberate accent (electric mint),
 * and a high-signal urgency scale used only for decision states.
 */
const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "Menlo", "monospace"],
      },
      colors: {
        bg: {
          primary: "#0B0F14",
          secondary: "#10161D",
          tertiary: "#161D25",
          elevated: "#1B232C",
        },
        fg: {
          primary: "#E6EDF3",
          secondary: "#A6B3C0",
          muted: "#6F7E8C",
          inverse: "#0B0F14",
        },
        border: {
          subtle: "#1F2731",
          DEFAULT: "#2A3540",
          strong: "#3A4756",
        },
        accent: {
          DEFAULT: "#46E5B5",
          hover: "#5BEEC0",
          muted: "#1E3A33",
        },
        // Decision urgency — used only for claim states, not generic UI.
        decision: {
          approve: "#46E5B5",
          deny: "#FF6B7A",
          review: "#F5C04D",
          fraud: "#D946EF",
        },
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 24px -12px rgba(0,0,0,0.5)",
      },
      borderRadius: {
        card: "10px",
      },
      animation: {
        "pulse-live": "pulseLive 2s ease-in-out infinite",
        "slide-in-right": "slideInRight 220ms cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        pulseLive: {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.5", transform: "scale(0.9)" },
        },
        slideInRight: {
          from: { transform: "translateX(24px)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
