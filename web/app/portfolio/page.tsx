import Link from "next/link";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";
import SegmentationPanel from "@/components/SegmentationPanel";
import { getPortfolio } from "@/lib/data";
import { inr, inrLakh } from "@/lib/format";

const DEC_COLOR: Record<string, string> = {
  approve: "#2f6b50",
  refer: "#b08433",
  decline: "#9e3b2e",
};

export default function PortfolioPage() {
  const pf = getPortfolio();
  const book = pf.demo_book;
  const cohort = pf.cohort;
  const segmentation = pf.segmentation;
  const counts = book.decision_counts;

  return (
    <>
      <SiteHeader active="portfolio" />
      <main className="relative z-[2] mx-auto max-w-5xl px-5 py-10">
        <header className="mb-8 max-w-3xl">
          <span className="eyebrow text-brass-deep">Bank-side view</span>
          <h1 className="mt-2 font-display text-4xl text-ink">Portfolio &amp; book lens</h1>
          <p className="mt-3 leading-relaxed text-ink-soft">
            Declines work at the same volume as approvals — Sehat reads as a risk
            filter, not an approval machine. Below: the demo book, then the cohort
            roll-up the score was validated on.
          </p>
        </header>

        {/* Decision mix */}
        <div className="card plate-ticks mb-8 grid gap-6 p-7 sm:grid-cols-4">
          <Tile label="Approve" value={counts.approve ?? 0} color={DEC_COLOR.approve} />
          <Tile label="Refer" value={counts.refer ?? 0} color={DEC_COLOR.refer} />
          <Tile label="Decline" value={counts.decline ?? 0} color={DEC_COLOR.decline} />
          <div>
            <div className="eyebrow text-ink-faint">Indicative exposure</div>
            <div className="mt-1 font-display text-3xl text-ink">
              {inrLakh(book.total_indicative_exposure)}
            </div>
            <div className="text-xs text-ink-faint">across approved personas</div>
          </div>
        </div>

        {/* Demo book table */}
        <section className="card mb-8 p-6">
          <h2 className="mb-3 font-display text-xl text-ink">Demo book</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-paper-line text-left font-mono text-[0.64rem] uppercase tracking-wider text-ink-faint">
                  <th className="py-2 pr-4">Entity</th>
                  <th className="py-2 pr-4">Sector</th>
                  <th className="py-2 pr-4">FHS</th>
                  <th className="py-2 pr-4">Band</th>
                  <th className="py-2 pr-4">Decision</th>
                  <th className="py-2 pr-4">Limit</th>
                  <th className="py-2">File</th>
                </tr>
              </thead>
              <tbody>
                {book.personas.map((p) => (
                  <tr key={p.id} className="border-b border-paper-line/40">
                    <td className="py-2 pr-4">
                      <Link href={`/card/${p.id}/`} className="text-ink hover:text-forest">
                        {p.name}
                      </Link>
                    </td>
                    <td className="py-2 pr-4 text-ink-soft">{p.sector.replace(/_/g, " ")}</td>
                    <td className="py-2 pr-4 font-mono">{p.fhs.toFixed(0)}</td>
                    <td className="py-2 pr-4 font-mono">{p.band}</td>
                    <td className="py-2 pr-4">
                      <span
                        className="rounded px-2 py-0.5 text-xs font-medium"
                        style={{ background: `${DEC_COLOR[p.decision]}14`, color: DEC_COLOR[p.decision] }}
                      >
                        {p.decision}
                      </span>
                    </td>
                    <td className="py-2 pr-4 font-mono text-ink-soft">
                      {p.indicative_limit > 0 ? inr(p.indicative_limit) : "—"}
                    </td>
                    <td className="py-2">
                      {p.thin_file ? (
                        <span className="font-mono text-[0.6rem] uppercase text-brass-deep">
                          thin
                        </span>
                      ) : (
                        <span className="font-mono text-[0.6rem] uppercase text-ink-faint">
                          on-file
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Cohort roll-up */}
        {cohort && (
          <section className="card p-6">
            <div className="mb-4 flex items-end justify-between">
              <h2 className="font-display text-xl text-ink">
                Validation cohort roll-up (n={cohort.n_test})
              </h2>
              <Link href="/validation/" className="text-sm text-forest hover:underline">
                Full report →
              </Link>
            </div>
            <div className="grid gap-3 sm:grid-cols-5">
              {cohort.bands.map((b) => (
                <div key={b.band} className="rounded-lg border border-paper-line bg-paper p-3">
                  <div className="font-mono text-lg text-ink">{b.band}</div>
                  <div className="mt-1 text-xs text-ink-faint">n={b.n}</div>
                  <div className="mt-1 text-sm font-medium text-ink-soft">
                    {(b.bad_rate * 100).toFixed(1)}% bad
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs text-ink-faint">
              AUC {cohort.auc.toFixed(3)} · KS {cohort.ks.toFixed(2)} · Gini{" "}
              {cohort.gini.toFixed(3)} · bad-rate monotone AA→D{" "}
              {cohort.bad_rate_monotone ? "✓" : "✗"} · base default rate{" "}
              {(cohort.base_default_rate * 100).toFixed(0)}%
            </p>
          </section>
        )}

        {/* Segmentation — the unified score cut by segment */}
        {segmentation && (
          <div className="mt-8">
            <SegmentationPanel seg={segmentation} />
          </div>
        )}
      </main>
      <SiteFooter />
    </>
  );
}

function Tile({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="eyebrow text-ink-faint">{label}</div>
      <div className="mt-1 font-display text-3xl" style={{ color }}>
        {value}
      </div>
    </div>
  );
}
