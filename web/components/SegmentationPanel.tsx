import type { SegmentationReport, SegmentStat } from "@/lib/types";
import { titleCase } from "@/lib/format";

/**
 * Segmentation panel — "the unified score, cut by segment".
 *
 * Answers the Jun-30 ask for a segmented-then-unified view: ONE FHS, sliced by
 * sector / state / constitution / vintage over the same held-out validation slice.
 * Descriptive only — no new scored sub-model, the spine is untouched. The clean
 * vintage gradient (older firms default less, approve more) is the headline read.
 */

const DIM_LABEL: Record<string, string> = {
  by_sector: "Sector",
  by_reg_type: "Constitution",
  by_vintage_band: "Vintage",
  by_state: "State",
};

// Bad-rate heat: green (low) → brass → clay (high), muted to the bank palette.
function heat(badRate: number, overall: number): string {
  const r = badRate / (overall || 1);
  if (r <= 0.6) return "#2f6b50";
  if (r <= 0.95) return "#4f8a6e";
  if (r <= 1.15) return "#b08433";
  if (r <= 1.6) return "#c0703a";
  return "#9e3b2e";
}

function DimensionTable({
  title,
  rows,
  overallBad,
}: {
  title: string;
  rows: SegmentStat[];
  overallBad: number;
}) {
  const maxBad = Math.max(...rows.map((r) => r.bad_rate), 0.0001);
  return (
    <div>
      <div className="eyebrow mb-2 text-ink-faint">{title}</div>
      <div className="space-y-1.5">
        {rows.map((s) => (
          <div key={s.segment} className="flex items-center gap-3 text-[0.8rem]">
            <span className="w-28 shrink-0 truncate text-ink-soft" title={titleCase(s.segment)}>
              {titleCase(s.segment)}
            </span>
            <span className="w-10 shrink-0 text-right font-mono text-[0.68rem] text-ink-faint">
              n={s.n}
            </span>
            <div className="relative h-3.5 flex-1 overflow-hidden rounded-sm bg-paper-deep">
              <div
                className="h-full rounded-sm transition-[width] duration-700"
                style={{
                  width: `${(s.bad_rate / maxBad) * 100}%`,
                  background: heat(s.bad_rate, overallBad),
                }}
              />
            </div>
            <span className="w-12 shrink-0 text-right font-mono text-[0.72rem] text-ink">
              {(s.bad_rate * 100).toFixed(1)}%
            </span>
            <span className="w-12 shrink-0 text-right font-mono text-[0.68rem] text-forest-mid">
              {(s.approve_rate * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function SegmentationPanel({ seg }: { seg: SegmentationReport }) {
  const overallBad = seg.overall.bad_rate;
  return (
    <section className="card p-6">
      <div className="mb-1 flex flex-wrap items-end justify-between gap-2">
        <h2 className="font-display text-xl text-ink">The unified score, cut by segment</h2>
        <span className="font-mono text-[0.64rem] uppercase tracking-wider text-ink-faint">
          held-out n={seg.n_test} · bad-rate / approve-rate
        </span>
      </div>
      <p className="mb-5 max-w-2xl text-[0.84rem] leading-relaxed text-ink-soft">
        One Financial Health Score, sliced across the book. Bars show the default
        (bad) rate per segment; the green figure is the approve-rate. Descriptive — the
        weights and validation spine are untouched.
      </p>
      <div className="grid gap-7 sm:grid-cols-2">
        <DimensionTable title={DIM_LABEL.by_vintage_band} rows={seg.by_vintage_band} overallBad={overallBad} />
        <DimensionTable title={DIM_LABEL.by_reg_type} rows={seg.by_reg_type} overallBad={overallBad} />
        <DimensionTable title={DIM_LABEL.by_sector} rows={seg.by_sector.slice(0, 6)} overallBad={overallBad} />
        <DimensionTable title={DIM_LABEL.by_state} rows={seg.by_state.slice(0, 6)} overallBad={overallBad} />
      </div>
      <p className="mt-5 border-t border-paper-line pt-3 text-[0.72rem] leading-relaxed text-ink-faint">
        Overall held-out bad-rate {(overallBad * 100).toFixed(1)}% · strata with n&lt;10
        suppressed. The vintage gradient (older firms default less, approve more) is the
        score behaving as a risk filter across segments, not just in aggregate.
      </p>
    </section>
  );
}
