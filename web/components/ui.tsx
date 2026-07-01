import type { Decision, Band, Reason, SubScore } from "@/lib/types";
import { DECISION_LABEL, SUBSCORE_LABELS } from "@/lib/format";

const DEC_STYLE: Record<Decision, { bg: string; fg: string; dot: string }> = {
  approve: { bg: "rgba(47,107,80,0.10)", fg: "#1f4d3a", dot: "#2f6b50" },
  refer: { bg: "rgba(176,132,51,0.12)", fg: "#8a6420", dot: "#b08433" },
  decline: { bg: "rgba(158,59,46,0.10)", fg: "#9e3b2e", dot: "#9e3b2e" },
};

export function DecisionBadge({ decision }: { decision: Decision }) {
  const s = DEC_STYLE[decision];
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[0.72rem] font-semibold uppercase tracking-wider"
      style={{ background: s.bg, color: s.fg }}
    >
      <span className="h-2 w-2 rounded-full" style={{ background: s.dot }} />
      {DECISION_LABEL[decision]}
    </span>
  );
}

export function BandChip({ band }: { band: Band }) {
  return (
    <span className="rounded-md border border-paper-line bg-paper px-2 py-0.5 font-mono text-xs font-semibold text-ink-soft">
      Band {band}
    </span>
  );
}

const POLARITY_MARK: Record<string, { glyph: string; color: string }> = {
  strength: { glyph: "✓", color: "#2f6b50" },
  risk: { glyph: "▲", color: "#9e3b2e" },
  neutral: { glyph: "·", color: "#6b7a70" },
  gate: { glyph: "◆", color: "#b08433" },
};

export function ReasonItem({ reason }: { reason: Reason }) {
  const m = POLARITY_MARK[reason.polarity] ?? POLARITY_MARK.neutral;
  return (
    <li className="group flex gap-3 py-2">
      <span
        className="mt-0.5 select-none text-sm font-bold leading-5"
        style={{ color: m.color }}
        aria-hidden
      >
        {m.glyph}
      </span>
      <div className="min-w-0">
        <p className="text-[0.92rem] leading-snug text-ink">{reason.narration}</p>
        <code className="mt-0.5 block font-mono text-[0.62rem] uppercase tracking-wide text-ink-faint opacity-70">
          {reason.code}
          {reason.used_llm && reason.grounded && (
            <span className="ml-2 text-forest-mid">narrated · grounded ✓</span>
          )}
        </code>
      </div>
    </li>
  );
}

const BAR_COLOR = (v: number) =>
  v >= 70 ? "#2f6b50" : v >= 55 ? "#b08433" : v >= 40 ? "#c0703a" : "#9e3b2e";

export function SubScoreBars({ subscores }: { subscores: SubScore[] }) {
  return (
    <div className="space-y-3">
      {subscores.map((s) => (
        <div key={s.name}>
          <div className="mb-1 flex items-baseline justify-between text-[0.78rem]">
            <span className="text-ink-soft">{SUBSCORE_LABELS[s.name] ?? s.name}</span>
            <span className="font-mono text-ink">
              {s.available ? s.value.toFixed(0) : "n/a"}
              <span className="ml-1.5 text-ink-faint">{Math.round(s.weight * 100)}%</span>
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-paper-deep">
            <div
              className="h-full rounded-full transition-[width] duration-700"
              style={{
                width: `${s.available ? s.value : 0}%`,
                background: BAR_COLOR(s.value),
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div>
      <div className="eyebrow text-ink-faint">{label}</div>
      <div className="mt-1 font-display text-2xl text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-faint">{sub}</div>}
    </div>
  );
}
