import { SiteHeader, SiteFooter } from "@/components/SiteChrome";
import BadRateChart from "@/components/BadRateChart";
import ModelCardPanel from "@/components/ModelCardPanel";
import { getValidation, getModelCard } from "@/lib/data";

export default function ValidationPage() {
  const v = getValidation();
  const lift = v.lift;
  const modelCard = getModelCard();

  return (
    <>
      <SiteHeader active="validation" />
      <main className="relative z-[2] mx-auto max-w-5xl px-5 py-10">
        <header className="mb-8 max-w-3xl">
          <span className="eyebrow text-brass-deep">The spine</span>
          <h1 className="mt-2 font-display text-4xl text-ink">
            It doesn&apos;t just explain — it separates good from bad.
          </h1>
          <p className="mt-3 leading-relaxed text-ink-soft">
            On a held-out slice of a {v.n_train + v.n_test}-entity labelled cohort
            ({v.n_train} train / {v.n_test} test), the deterministic score reports
            real discrimination. A latent repayment propensity drives both the noisy
            features and a seeded default label, so the AUC is honest, not circular.
          </p>
        </header>

        {/* Headline metrics */}
        <div className="card plate-ticks mb-8 grid grid-cols-2 gap-6 p-7 sm:grid-cols-4">
          <Big label="AUC" value={v.auc.toFixed(3)} />
          <Big label="Gini" value={v.gini.toFixed(3)} />
          <Big label="KS" value={v.ks.toFixed(2)} />
          <Big
            label="Bad-rate AA→D"
            value={v.bad_rate_monotone ? "monotone ✓" : "✗"}
            small
          />
        </div>

        <div className="grid gap-7 lg:grid-cols-2">
          {/* Bad rate by band */}
          <section className="card p-6">
            <h2 className="mb-1 font-display text-xl text-ink">Bad rate by band</h2>
            <p className="mb-3 text-sm text-ink-faint">
              Monotonically decreasing risk from D up to AA — the ordering a bank prices on.
            </p>
            <BadRateChart bands={v.bands} />
          </section>

          {/* Credit-Invisible Lift */}
          <section className="card p-6">
            <h2 className="mb-1 font-display text-xl text-ink">Credit-Invisible Lift</h2>
            <p className="mb-4 text-sm text-ink-faint">
              On the thin/no-file reject cohort (n={lift.reject_cohort_n}) a bureau
              scorecard cannot price.
            </p>
            <div className="space-y-3">
              <LiftRow
                label="Sehat approves"
                value={`${lift.sehat_approved_n} of ${lift.reject_cohort_n} · ${Math.round(lift.approval_rate * 100)}%`}
              />
              <LiftRow
                label="…at a bad rate of"
                value={`${(lift.approved_bad_rate * 100).toFixed(1)}%`}
                tone="good"
              />
              <LiftRow
                label="Those it declines default at"
                value={`${(lift.declined_bad_rate * 100).toFixed(1)}%`}
                tone="bad"
              />
              <LiftRow
                label="Cohort baseline"
                value={`${(lift.baseline_bad_rate * 100).toFixed(1)}%`}
              />
              <div className="mt-4 rounded-lg bg-forest/[0.06] p-4">
                <div className="font-display text-2xl text-forest-deep">
                  +{(lift.bad_rate_reduction_vs_blanket * 100).toFixed(1)}pt
                </div>
                <div className="text-sm text-ink-soft">
                  bad-rate reduction vs blanket-approving the cohort — expands the book
                  while holding losses under appetite.
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Gains / lift table */}
        <section className="card mt-7 overflow-hidden p-6">
          <h2 className="mb-3 font-display text-xl text-ink">Gains / lift by risk decile</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-paper-line text-left font-mono text-[0.66rem] uppercase tracking-wider text-ink-faint">
                  <th className="py-2 pr-4">Decile</th>
                  <th className="py-2 pr-4">n</th>
                  <th className="py-2 pr-4">Bad rate</th>
                  <th className="py-2 pr-4">Lift</th>
                  <th className="py-2">Cum % defaults</th>
                </tr>
              </thead>
              <tbody className="font-mono text-ink-soft">
                {v.gains.map((g) => (
                  <tr key={g.decile} className="border-b border-paper-line/40">
                    <td className="py-1.5 pr-4">{g.decile}</td>
                    <td className="py-1.5 pr-4">{g.n}</td>
                    <td className="py-1.5 pr-4">{(g.bad_rate * 100).toFixed(1)}%</td>
                    <td className="py-1.5 pr-4">{g.lift.toFixed(2)}×</td>
                    <td className="py-1.5">{(g.cum_pct_defaults * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Hybrid: champion + challenger model card */}
        {modelCard && <ModelCardPanel mc={modelCard} />}

        <div className="mt-6 space-y-1.5 rounded-lg bg-ink/[0.03] p-4 text-xs leading-relaxed text-ink-faint">
          {v.notes.map((n, i) => (
            <p key={i}>· {n}</p>
          ))}
        </div>
      </main>
      <SiteFooter />
    </>
  );
}

function Big({ label, value, small }: { label: string; value: string; small?: boolean }) {
  return (
    <div>
      <div className="eyebrow text-ink-faint">{label}</div>
      <div className={`mt-1 font-display text-ink ${small ? "text-xl" : "text-4xl"}`}>
        {value}
      </div>
    </div>
  );
}

function LiftRow({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  const c = tone === "good" ? "#2f6b50" : tone === "bad" ? "#9e3b2e" : "#1c2b25";
  return (
    <div className="flex items-baseline justify-between border-b border-paper-line/40 pb-2">
      <span className="text-sm text-ink-soft">{label}</span>
      <span className="font-mono text-base font-semibold" style={{ color: c }}>
        {value}
      </span>
    </div>
  );
}
