import Link from "next/link";
import { SiteHeader, SiteFooter } from "@/components/SiteChrome";
import { getPersonas, getValidation } from "@/lib/data";
import { inrLakh } from "@/lib/format";

export default function Home() {
  const personas = getPersonas();
  const v = getValidation();
  const lift = v.lift;

  return (
    <>
      <SiteHeader />
      <main className="relative z-[2] mx-auto max-w-6xl px-5">
        {/* Hero */}
        <section className="grid items-center gap-10 py-14 lg:grid-cols-[1.1fr_0.9fr] lg:py-20">
          <div className="rise">
            <div className="eyebrow mb-4 inline-flex items-center gap-2 rounded-full border border-brass/30 bg-brass/5 px-3 py-1 text-brass-deep">
              IDBI Innovate 2026 · Track 03
            </div>
            <h1 className="font-display text-4xl leading-[1.05] text-ink sm:text-5xl md:text-6xl">
              The credit score that
              <span className="text-forest"> shows its work.</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-soft">
              Sehat aggregates a New-to-Credit (NTC) MSME&apos;s alternate data — GST, UPI,
              bank, EPFO, even operational meters — into a deterministic, validated,
              governed Financial Health Card. An underwriter assistant that approves
              blank-slate businesses a bureau would reject, proves it separates good from
              bad on a labelled cohort, and shows its work — the human keeps the decision.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/card/P2_HERO/"
                className="rounded-lg bg-forest px-5 py-3 text-sm font-medium text-paper shadow-plate transition-transform hover:-translate-y-0.5"
              >
                Open the Health Card →
              </Link>
              <Link
                href="/validation/"
                className="rounded-lg border border-ink/15 px-5 py-3 text-sm font-medium text-ink transition-colors hover:bg-ink/5"
              >
                See the validation spine
              </Link>
            </div>
          </div>

          {/* Headline metric plate */}
          <div className="card plate-ticks rise p-7" style={{ animationDelay: "0.12s" }}>
            <div className="eyebrow text-ink-faint">The differentiator — Credit-Invisible Lift</div>
            <p className="mt-3 text-[0.92rem] leading-relaxed text-ink-soft">
              Across a thin-file <em>reject</em> cohort a bureau scorecard can&apos;t price,
              Sehat safely extends credit:
            </p>
            <div className="mt-5 grid grid-cols-2 gap-5">
              <Metric big={`${Math.round(lift.approval_rate * 100)}%`} label="approved" />
              <Metric big={`${(lift.approved_bad_rate * 100).toFixed(1)}%`} label="bad rate on approved" tone="good" />
              <Metric big={`${(lift.declined_bad_rate * 100).toFixed(0)}%`} label="bad rate on declined" tone="bad" />
              <Metric big={`+${(lift.bad_rate_reduction_vs_blanket * 100).toFixed(0)}pt`} label="vs blanket-approve" tone="good" />
            </div>
            <div className="mt-5 flex items-center gap-4 border-t border-paper-line pt-4 font-mono text-xs text-ink-faint">
              <span>AUC {v.auc.toFixed(3)}</span>
              <span>·</span>
              <span>KS {v.ks.toFixed(2)}</span>
              <span>·</span>
              <span>bad-rate monotone AA→D ✓</span>
            </div>
          </div>
        </section>

        {/* Persona gallery */}
        <section className="pb-10">
          <div className="mb-5 flex items-end justify-between">
            <h2 className="font-display text-2xl text-ink">{personas.length} demo personas</h2>
            <span className="text-sm text-ink-faint">switchable live — same engine, frozen inputs</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {personas.map((p, i) => (
              <Link
                key={p.id}
                href={`/card/${p.id}/`}
                className="card rise group p-5 transition-transform hover:-translate-y-1"
                style={{ animationDelay: `${i * 0.05}s` }}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[0.62rem] text-ink-faint">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <DecisionTag decision={p.decision} />
                </div>
                <h3 className="mt-2 font-display text-xl text-ink">{p.name}</h3>
                <p className="mt-1.5 line-clamp-3 text-[0.82rem] leading-snug text-ink-soft">
                  {p.tagline}
                </p>
                <div className="mt-4 flex items-center justify-between border-t border-paper-line pt-3">
                  <span className="font-mono text-sm text-ink">
                    FHS {p.fhs.toFixed(0)} · {p.band}
                  </span>
                  <span className="text-sm text-ink-faint">
                    {p.indicative_limit > 0 ? inrLakh(p.indicative_limit) : "—"}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

function Metric({ big, label, tone }: { big: string; label: string; tone?: "good" | "bad" }) {
  const color = tone === "good" ? "#2f6b50" : tone === "bad" ? "#9e3b2e" : "#1c2b25";
  return (
    <div>
      <div className="font-display text-3xl" style={{ color }}>
        {big}
      </div>
      <div className="mt-0.5 text-xs text-ink-faint">{label}</div>
    </div>
  );
}

function DecisionTag({ decision }: { decision: string }) {
  const map: Record<string, { c: string; t: string }> = {
    approve: { c: "#2f6b50", t: "approve" },
    refer: { c: "#b08433", t: "refer" },
    decline: { c: "#9e3b2e", t: "decline" },
  };
  const d = map[decision] ?? map.refer;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[0.62rem] font-semibold uppercase tracking-wider"
      style={{ background: `${d.c}14`, color: d.c }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: d.c }} />
      {d.t}
    </span>
  );
}
