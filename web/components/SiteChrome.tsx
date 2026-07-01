import Link from "next/link";
import { SCORECARD_VERSION } from "@/lib/data";

export function SiteHeader({ active }: { active?: "card" | "portfolio" | "validation" }) {
  const link = (href: string, label: string, key: string) => (
    <Link
      href={href}
      className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
        active === key
          ? "bg-forest/[0.08] font-medium text-forest-deep"
          : "text-ink-soft hover:text-ink"
      }`}
    >
      {label}
    </Link>
  );
  return (
    <header className="relative z-10 border-b border-paper-line/70 bg-paper/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3.5">
        <Link href="/" className="flex items-center gap-3">
          <Mark />
          <div className="leading-tight">
            <div className="font-display text-lg text-ink">Sehat</div>
            <div className="font-mono text-[0.58rem] uppercase tracking-[0.2em] text-ink-faint">
              MSME Health Card
            </div>
          </div>
        </Link>
        <nav className="flex items-center gap-1">
          {link("/card/P2_HERO/", "Health Card", "card")}
          {link("/portfolio/", "Portfolio", "portfolio")}
          {link("/validation/", "Validation", "validation")}
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="relative z-10 mt-16 border-t border-paper-line/70 py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-5 text-center">
        <div className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-ink-faint">
          ULI (data in) → Sehat engine → OCEN (offer out)
        </div>
        <p className="text-xs text-ink-faint">
          Team SehatAI · IDBI Innovate 2026 · Track 03 · Scorecard v{SCORECARD_VERSION} ·
          synthetic data calibrated to RBI/MSME distributions, pending sandbox validation
        </p>
      </div>
    </footer>
  );
}

function Mark() {
  // A small etched "leaf-in-circle" — health + the forest ink palette.
  return (
    <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden>
      <circle cx="17" cy="17" r="15.5" fill="none" stroke="#1f4d3a" strokeWidth="1.3" />
      <circle cx="17" cy="17" r="15.5" fill="none" stroke="#b08433" strokeWidth="1.3" strokeDasharray="2 4" opacity="0.5" />
      <path
        d="M17 25 C 11 22, 10 14, 17 9 C 24 14, 23 22, 17 25 Z"
        fill="#2f6b50"
        fillOpacity="0.18"
        stroke="#1f4d3a"
        strokeWidth="1.2"
      />
      <path d="M17 25 L 17 13" stroke="#1f4d3a" strokeWidth="1.2" />
    </svg>
  );
}
