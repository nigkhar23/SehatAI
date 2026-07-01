import type { Config } from "tailwindcss";

/**
 * "Precision instrument on fine ledger paper" — a warm bone/parchment ground,
 * deep-evergreen ink, brass accents. The opposite of dark-fintech cliché: this
 * reads as a bank's considered, auditable instrument, not a crypto dashboard.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: "#f4efe4", // bone / parchment
          deep: "#ece4d3",
          card: "#fbf8f0",
          line: "#ddd2bb",
        },
        ink: {
          DEFAULT: "#1c2b25", // deep evergreen-black
          soft: "#3a4a42",
          faint: "#6b7a70",
        },
        forest: {
          DEFAULT: "#1f4d3a",
          deep: "#143329",
          mid: "#2f6b50",
          light: "#4f8a6e",
        },
        brass: {
          DEFAULT: "#b08433",
          light: "#caa55a",
          deep: "#8a6420",
        },
        // Decision semantics — muted, bank-appropriate, never neon.
        approve: "#2f6b50",
        refer: "#b08433",
        decline: "#9e3b2e",
        clay: "#9e3b2e",
      },
      fontFamily: {
        display: ["var(--font-fraunces)", "Georgia", "serif"],
        sans: ["var(--font-archivo)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 0 #fff inset, 0 18px 40px -24px rgba(28,43,37,0.45)",
        plate: "0 1px 2px rgba(28,43,37,0.08), 0 12px 30px -18px rgba(28,43,37,0.35)",
        inset: "inset 0 2px 6px rgba(28,43,37,0.08)",
      },
      backgroundImage: {
        grain:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E\")",
      },
      keyframes: {
        "rise": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "draw": {
          "0%": { strokeDashoffset: "var(--dash)" },
          "100%": { strokeDashoffset: "0" },
        },
      },
      animation: {
        rise: "rise 0.6s cubic-bezier(0.2,0.7,0.2,1) both",
      },
    },
  },
  plugins: [],
};

export default config;
