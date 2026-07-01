import type { ModelCrossCheck as MCC, ShapContribution, ChampionContribution } from "@/lib/types";

// The champion/challenger cross-check — the "AI a bank is allowed to deploy" panel.
// Three INDEPENDENT verdicts (deterministic FHS, learned WOE scorecard, monotone GBM)
// shown side by side, then each model's top per-applicant drivers. The FHS still
// decides; these are validated second opinions. When all three agree -> high
// confidence; when they disagree -> the governance gate routes to human review.
export default function ModelCrossCheck({ mcc }: { mcc: MCC }) {
  const { champion, challenger, cross_check: xc } = mcc;
  const agree = xc.agree;

  return (
    <div className="rounded-xl border border-paper-line bg-paper-card/60">
      <div className="flex items-center justify-between border-b border-paper-line px-5 py-3.5">
        <span className="eyebrow text-ink-soft">
          Model cross-check — champion · challenger · score
        </span>
        <AgreeBadge agree={agree} />
      </div>

      <div className="space-y-5 px-5 py-4">
        {/* Three verdicts */}
        <div className="grid gap-3 sm:grid-cols-3">
          <Verdict
            title="Deterministic score"
            sub="FHS band policy · decides"
            approve={xc.fhs_approve}
            metric={null}
          />
          <Verdict
            title="Champion scorecard"
            sub="WOE + logistic · readable"
            approve={xc.champion_approve}
            metric={champion ? { label: "PD", value: champion.pd, thr: champion.threshold } : null}
          />
          <Verdict
            title="Challenger model"
            sub="Monotonic GBM + SHAP · advises"
            approve={xc.challenger_approve}
            metric={challenger ? { label: "PD", value: challenger.pd, thr: challenger.threshold } : null}
          />
        </div>

        {/* Agreement note */}
        <p
          className="rounded-lg px-4 py-2.5 text-[0.82rem] leading-relaxed"
          style={{
            background: agree ? "rgba(47,107,80,0.08)" : "rgba(176,132,51,0.12)",
            color: agree ? "#1f4d3a" : "#8a6420",
          }}
        >
          {xc.note}
        </p>

        {/* Per-applicant drivers */}
        <div className="grid gap-5 lg:grid-cols-2">
          {champion && (
            <div>
              <div className="eyebrow mb-2 text-ink-faint">
                Champion — scorecard points (higher = safer)
              </div>
              <ChampionDrivers contributions={champion.contributions} />
            </div>
          )}
          {challenger && (
            <div>
              <div className="eyebrow mb-2 text-ink-faint">
                Challenger — SHAP attribution (per applicant)
              </div>
              <ShapDrivers contributions={challenger.contributions} />
            </div>
          )}
        </div>

        <p className="text-[0.7rem] leading-relaxed text-ink-faint">
          Both models are <span className="text-ink-soft">trained on the labelled cohort</span> and{" "}
          <span className="text-ink-soft">monotone by construction</span> (no &ldquo;more bounces →
          safer&rdquo;). Computed offline and frozen — the card makes zero live model calls. The
          score decides; the champion explains; the challenger checks.
        </p>
      </div>
    </div>
  );
}

function AgreeBadge({ agree }: { agree: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[0.6rem] font-semibold uppercase tracking-wider"
      style={{
        background: agree ? "rgba(47,107,80,0.12)" : "rgba(176,132,51,0.14)",
        color: agree ? "#1f4d3a" : "#8a6420",
      }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: agree ? "#2f6b50" : "#b08433" }}
      />
      {agree ? "models agree" : "review — disagreement"}
    </span>
  );
}

function Verdict({
  title,
  sub,
  approve,
  metric,
}: {
  title: string;
  sub: string;
  approve: boolean | null;
  metric: { label: string; value: number; thr: number } | null;
}) {
  const tone =
    approve === null ? "#6b7a70" : approve ? "#2f6b50" : "#9e3b2e";
  const word = approve === null ? "n/a" : approve ? "approve" : "no-go";
  return (
    <div className="rounded-lg border border-paper-line bg-paper px-3.5 py-3">
      <div className="font-display text-[0.95rem] leading-tight text-ink">{title}</div>
      <div className="mt-0.5 text-[0.66rem] uppercase tracking-wide text-ink-faint">{sub}</div>
      <div className="mt-2 flex items-baseline justify-between">
        <span className="text-sm font-semibold" style={{ color: tone }}>
          {word}
        </span>
        {metric && (
          <span className="font-mono text-[0.7rem] text-ink-faint">
            {metric.label} {(metric.value * 100).toFixed(1)}%
            <span className="opacity-60"> / {(metric.thr * 100).toFixed(0)}%</span>
          </span>
        )}
      </div>
    </div>
  );
}

// Champion: signed scorecard points. We show deviation from the mean contribution as a
// diverging bar (right = adds points = safer; left = subtracts = riskier).
function ChampionDrivers({ contributions }: { contributions: ChampionContribution[] }) {
  const top = contributions.slice(0, 6);
  const mean =
    contributions.reduce((s, c) => s + c.points, 0) / Math.max(1, contributions.length);
  const max = Math.max(...top.map((c) => Math.abs(c.points - mean)), 1);
  return (
    <ul className="space-y-1.5">
      {top.map((c) => {
        const dev = c.points - mean;
        const pct = (Math.abs(dev) / max) * 50;
        const pos = dev >= 0;
        return (
          <li key={c.key} className="flex items-center gap-2 text-[0.78rem]">
            <span className="w-32 shrink-0 truncate text-ink-soft" title={c.label}>
              {c.label}
            </span>
            <div className="relative h-3 flex-1 rounded-sm bg-paper-deep">
              <div className="absolute left-1/2 top-0 h-full w-px bg-paper-line" />
              <div
                className="absolute top-0 h-full rounded-sm"
                style={{
                  background: pos ? "#2f6b50" : "#9e3b2e",
                  width: `${pct}%`,
                  left: pos ? "50%" : `${50 - pct}%`,
                }}
              />
            </div>
            <span className="w-10 shrink-0 text-right font-mono text-[0.68rem] text-ink-faint">
              {pos ? "+" : ""}
              {dev.toFixed(0)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

// Challenger: SHAP push on log-odds of default. shap>0 = adds risk (left, clay);
// shap<0 = reduces risk (right, forest).
function ShapDrivers({ contributions }: { contributions: ShapContribution[] }) {
  const top = contributions.slice(0, 6);
  const max = Math.max(...top.map((c) => Math.abs(c.shap)), 1e-6);
  return (
    <ul className="space-y-1.5">
      {top.map((c) => {
        const reduces = c.shap < 0; // reduces risk -> good -> right/forest
        const pct = (Math.abs(c.shap) / max) * 50;
        return (
          <li key={c.key} className="flex items-center gap-2 text-[0.78rem]">
            <span className="w-32 shrink-0 truncate text-ink-soft" title={c.label}>
              {c.label}
            </span>
            <div className="relative h-3 flex-1 rounded-sm bg-paper-deep">
              <div className="absolute left-1/2 top-0 h-full w-px bg-paper-line" />
              <div
                className="absolute top-0 h-full rounded-sm"
                style={{
                  background: reduces ? "#2f6b50" : "#9e3b2e",
                  width: `${pct}%`,
                  left: reduces ? "50%" : `${50 - pct}%`,
                }}
              />
            </div>
            <span className="w-10 shrink-0 text-right font-mono text-[0.68rem] text-ink-faint">
              {c.shap > 0 ? "+" : ""}
              {c.shap.toFixed(2)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
