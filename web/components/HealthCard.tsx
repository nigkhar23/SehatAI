import type { Assessment } from "@/lib/types";
import { inr, BAND_LABEL, titleCase } from "@/lib/format";
import Gauge from "./Gauge";
import SubScoreRadar from "./SubScoreRadar";
import CoverageMeter from "./CoverageMeter";
import GateStrip from "./GateStrip";
import WhyDrawer from "./WhyDrawer";
import ModelCrossCheck from "./ModelCrossCheck";
import OperationalProxyPanel from "./OperationalProxyPanel";
import { DecisionBadge, BandChip, ReasonItem, SubScoreBars, Stat } from "./ui";

export default function HealthCard({ a }: { a: Assessment }) {
  const e = a.entity;
  return (
    <div className="card plate-ticks rise overflow-hidden">
      {/* Header */}
      <div className="flex flex-col gap-4 px-6 pt-7 sm:px-9 sm:pt-9 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="font-display text-2xl text-ink sm:text-[1.7rem]">{e.name}</h2>
            {a.bureau_thin_file && (
              <span className="rounded-full border border-brass/40 bg-brass/10 px-2.5 py-0.5 font-mono text-[0.58rem] uppercase tracking-wider text-brass-deep">
                ● credit-invisible
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-ink-faint">
            {titleCase(e.sector)} · {e.state} · {titleCase(e.reg_type)} ·{" "}
            {e.vintage_months} mo vintage
          </p>
          <p className="mt-3 max-w-xl text-[0.9rem] italic leading-relaxed text-ink-soft">
            {e.tagline}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-start gap-2 md:items-end">
          <DecisionBadge decision={a.decision} />
          <BandChip band={a.band} />
        </div>
      </div>

      <div className="mt-6 h-px bg-paper-line" />

      {/* Gauge + radar + sizing */}
      <div className="grid gap-6 px-6 py-7 sm:px-9 lg:grid-cols-[280px_1fr_minmax(200px,240px)]">
        <div className="flex flex-col items-center">
          <Gauge value={a.fhs} band={a.band} />
          <div className="mt-1 text-center">
            <div className="font-display text-lg text-ink">{BAND_LABEL[a.band]}</div>
          </div>
        </div>

        <div className="flex flex-col justify-center">
          <span className="eyebrow text-ink-faint">Six explainable sub-scores</span>
          <SubScoreRadar subscores={a.subscores} />
        </div>

        <div className="flex flex-col justify-center gap-5 border-t border-paper-line pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          {a.decision === "approve" ? (
            <>
              <Stat
                label="Recommended eligibility"
                value={inr(a.indicative_limit)}
                sub="indicative — not a sanction"
              />
              <Stat
                label="Post-loan DSCR"
                value={a.post_loan_dscr?.toFixed(2) ?? "—"}
                sub="target ≥ 1.30–1.50"
              />
            </>
          ) : (
            <Stat
              label={a.decision === "decline" ? "Outcome" : "Outcome"}
              value={a.decision === "decline" ? "No offer" : "Manual review"}
              sub={
                a.blocking_gate
                  ? `gate: ${a.blocking_gate}`
                  : `band ${a.band} policy`
              }
            />
          )}
          <p className="text-[0.7rem] leading-relaxed text-ink-faint">
            A yes-go / no-go recommendation for the underwriter — indicative eligibility,
            subject to KYC, credit policy &amp; KFS. A binding sanction is the bank&apos;s
            act, not the score.
          </p>
        </div>
      </div>

      <div className="px-6 sm:px-9">
        <div className="h-px bg-paper-line" />
      </div>

      {/* Sub-score bars (full breakdown) */}
      <div className="grid gap-7 px-6 py-7 sm:px-9 lg:grid-cols-2">
        <div>
          <span className="eyebrow mb-3 block text-ink-faint">Sub-score breakdown · fitted weights</span>
          <SubScoreBars subscores={a.subscores} />
        </div>
        <div>
          <span className="eyebrow mb-2 block text-ink-faint">Data &amp; consent</span>
          <CoverageMeter coverage={a.coverage} />
          <div className="mt-4">
            <GateStrip assessment={a} />
          </div>
          {a.operational_proxy && (
            <div className="mt-4">
              <OperationalProxyPanel proxy={a.operational_proxy} />
            </div>
          )}
        </div>
      </div>

      <div className="px-6 sm:px-9">
        <div className="h-px bg-paper-line" />
      </div>

      {/* Strengths & risks */}
      <div className="grid gap-7 px-6 py-7 sm:px-9 lg:grid-cols-2">
        <div>
          <h3 className="mb-1 font-display text-lg text-forest-deep">Strengths</h3>
          <ul className="divide-y divide-paper-line/50">
            {a.strengths.length ? (
              a.strengths.map((r) => <ReasonItem key={r.code} reason={r} />)
            ) : (
              <li className="py-3 text-sm text-ink-faint">None surfaced.</li>
            )}
          </ul>
        </div>
        <div>
          <h3 className="mb-1 font-display text-lg text-clay">Risks &amp; watch-items</h3>
          <ul className="divide-y divide-paper-line/50">
            {a.risks.length ? (
              a.risks.map((r) => <ReasonItem key={r.code} reason={r} />)
            ) : (
              <li className="py-3 text-sm text-ink-faint">None surfaced.</li>
            )}
          </ul>
          {a.notes.length > 0 && (
            <div className="mt-4">
              <span className="eyebrow text-ink-faint">Notes</span>
              <ul className="mt-1 divide-y divide-paper-line/40">
                {a.notes.map((r) => (
                  <ReasonItem key={r.code} reason={r} />
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Conventional-vs-Sehat caption */}
      <div className="mx-6 mb-6 rounded-xl bg-ink/[0.035] p-5 sm:mx-9">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="border-l-2 border-clay/40 pl-4">
            <div className="eyebrow text-clay/80">Conventional bureau scorecard</div>
            <p className="mt-1 text-[0.86rem] leading-relaxed text-ink-soft">
              {a.bureau_thin_file
                ? "Thin / no bureau file → cannot price this borrower → generic decline."
                : "Has a bureau file, but underwrites on bureau history alone — blind to live cash-flow and formalization."}
            </p>
          </div>
          <div className="border-l-2 border-forest/50 pl-4">
            <div className="eyebrow text-forest">Sehat · underwriter assistant</div>
            <p className="mt-1 text-[0.86rem] leading-relaxed text-ink-soft">
              {a.decision === "approve"
                ? a.model_cross_check?.cross_check?.agree === false
                  ? "Approved on the Financial Health Score — but the champion and challenger models split, so this is flagged for a human reviewer. The score decides; the models advise; the disagreement is disclosed."
                  : "Reads alternate data (GST / UPI / bank / EPFO), validates discrimination, and shows its work — here's why."
                : a.blocking_gate === "bureau"
                  ? "Strong alternate-data profile, but a live bureau marker is a hard stop — bureau is necessary, not sufficient."
                  : a.decision === "refer" && a.model_cross_check?.cross_check?.agree === false
                    ? "A borderline case where the models disagree — Sehat doesn't guess, it routes to a human reviewer. Governance built in."
                    : a.decision === "refer"
                      ? "A conditional, borderline profile — Sehat refers it for a human decision rather than forcing a yes or no."
                      : "Says no when the fundamentals say no — a risk filter, not an approval machine."}
            </p>
          </div>
        </div>
      </div>

      {/* Model cross-check (champion + challenger) + Why drawer */}
      <div className="space-y-4 px-6 pb-7 sm:px-9">
        {a.model_cross_check && <ModelCrossCheck mcc={a.model_cross_check} />}
        <WhyDrawer assessment={a} />
      </div>
    </div>
  );
}
