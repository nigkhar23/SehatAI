import type { OperationalProxy } from "@/lib/types";

/**
 * Operational-proxy panel — the Track-03 owner's explicit ask, in product.
 *
 * Reads a physical-world meter (electricity / water / fuel) that corroborates a
 * thin tax/UPI file: steady consumption says the unit is running at capacity; a
 * sharp recent drop says a possible slowdown (his literal "electricity dropped 40%
 * over 3 months" example). The same engine mechanism drives both — here we render
 * the series as a hand-drawn sparkline with the recent window called out, plus the
 * machine verdict badge. Numbers come straight off the engine's derived features.
 */

const PROXY_META: Record<string, { label: string; icon: string }> = {
  electricity: { label: "Electricity", icon: "⚡" },
  water: { label: "Water", icon: "💧" },
  fuel: { label: "Fuel", icon: "⛽" },
};

function verdict(breakPct: number | null) {
  // Mirrors the scoring thresholds in scoring.py (steady >= -8%, break <= -15%).
  if (breakPct === null)
    return { tone: "neutral" as const, text: "Series present", fg: "#6b7a70", bg: "rgba(107,122,112,0.10)" };
  if (breakPct <= -15)
    return {
      tone: "risk" as const,
      text: `Down ${Math.abs(breakPct).toFixed(0)}% recently — possible slowdown`,
      fg: "#9e3b2e",
      bg: "rgba(158,59,46,0.10)",
    };
  if (breakPct >= -8)
    return {
      tone: "strength" as const,
      text: "Steady — operating at capacity",
      fg: "#1f4d3a",
      bg: "rgba(47,107,80,0.10)",
    };
  return {
    tone: "neutral" as const,
    text: `${breakPct > 0 ? "+" : ""}${breakPct.toFixed(0)}% recent vs baseline`,
    fg: "#8a6420",
    bg: "rgba(176,132,51,0.12)",
  };
}

function Sparkline({ proxy, lineColor }: { proxy: OperationalProxy; lineColor: string }) {
  const vals = proxy.series.map((p) => p.value);
  if (vals.length < 2) return null;
  const W = 320;
  const H = 64;
  const PAD = 4;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const n = vals.length;
  const x = (i: number) => PAD + (i / (n - 1)) * (W - 2 * PAD);
  // Headroom so the line never clips against the top/bottom edges.
  const y = (v: number) => H - PAD - ((v - min) / span) * (H - 2 * PAD - 8) - 4;

  const pts = vals.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `${PAD},${H - PAD} ${pts} ${W - PAD},${H - PAD}`;

  // Recent window = last `recent_window_months` points (the comparison the engine made).
  const win = Math.min(proxy.recent_window_months || 3, n - 1);
  const recentStartX = x(n - win);

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible" role="img"
         aria-label={`${proxy.type} consumption over ${n} months`}>
      {/* Recent-window shaded band — what the trend-break compares against baseline */}
      <rect x={recentStartX} y={0} width={W - PAD - recentStartX} height={H}
            fill="rgba(176,132,51,0.08)" />
      <polygon points={area} fill={lineColor} opacity={0.07} />
      <polyline points={pts} fill="none" stroke={lineColor} strokeWidth={1.8}
                strokeLinejoin="round" strokeLinecap="round" />
      {vals.map((v, i) => (
        <circle key={i} cx={x(i)} cy={y(v)} r={i >= n - win ? 2.4 : 1.5}
                fill={i >= n - win ? lineColor : "#fbf8f0"} stroke={lineColor}
                strokeWidth={1} />
      ))}
    </svg>
  );
}

export default function OperationalProxyPanel({ proxy }: { proxy: OperationalProxy }) {
  const meta = PROXY_META[proxy.type] ?? { label: proxy.type, icon: "◆" };
  const v = verdict(proxy.recent_break_pct);
  const lineColor = v.tone === "risk" ? "#9e3b2e" : "#2f6b50";
  const first = proxy.series[0];
  const last = proxy.series[proxy.series.length - 1];

  return (
    <div className="rounded-xl border border-paper-line bg-paper-card p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <span className="eyebrow text-ink-faint">Operational proxy · alternate data</span>
          <h4 className="mt-0.5 font-display text-lg text-ink">
            <span aria-hidden className="mr-1.5">{meta.icon}</span>
            {meta.label} consumption
          </h4>
        </div>
        <span
          className="shrink-0 rounded-full px-2.5 py-1 text-[0.68rem] font-semibold"
          style={{ color: v.fg, background: v.bg }}
        >
          {v.text}
        </span>
      </div>

      <Sparkline proxy={proxy} lineColor={lineColor} />

      <div className="mt-2 flex items-center justify-between font-mono text-[0.62rem] uppercase tracking-wide text-ink-faint">
        <span>{first?.period}</span>
        <span>
          {proxy.series.length} mo · last {proxy.recent_window_months} highlighted
        </span>
        <span>{last?.period}</span>
      </div>

      <p className="mt-3 text-[0.8rem] leading-relaxed text-ink-soft">
        A physical-world signal a bureau scorecard never sees. When the GST/UPI file is
        thin, a steady meter corroborates that the business is genuinely operating — the
        same mechanism flags a sharp drop as a slowdown.
      </p>
    </div>
  );
}
