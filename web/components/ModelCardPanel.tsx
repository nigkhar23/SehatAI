import type { ModelCard } from "@/lib/types";

// Validation-page panel for the hybrid: three models' AUC side by side, their
// approve-agreement, and the LEARNED Information-Value feature ranking. This is the
// "not too simple / modern ML + bank-standard interpretability" evidence the deck
// leads on — champion/challenger is exactly how a real risk team operates.
export default function ModelCardPanel({ mc }: { mc: ModelCard }) {
  const ag = mc.agreement;
  const maxIv = Math.max(...mc.information_value_ranking.map((r) => r.iv), 0.01);

  return (
    <section className="card mt-7 p-7">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-display text-xl text-ink">Champion &amp; challenger — model cross-check</h2>
        <span className="font-mono text-[0.66rem] uppercase tracking-wider text-ink-faint">
          held-out n={mc.n_test} · train n={mc.n_train}
        </span>
      </div>
      <p className="mb-5 max-w-3xl text-sm text-ink-faint">
        A learned <span className="text-ink-soft">WOE + logistic scorecard</span> (champion, decides
        &amp; explains) cross-checked by a <span className="text-ink-soft">monotonic gradient-boosting
        model</span> (challenger, advises) — both trained on the same labelled cohort, both monotone
        by construction. The deterministic FHS remains the interpretable face.
      </p>

      {/* AUC trio */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <AucCard
          name="Champion"
          sub="WOE + logistic"
          auc={mc.champion.auc}
          note="readable · RBI-explainable"
          accent="#1f4d3a"
        />
        <AucCard
          name="Challenger"
          sub="Monotonic LightGBM"
          auc={mc.challenger.auc}
          note={`+SHAP · ${mc.challenger.num_boost_round} trees`}
          accent="#b08433"
        />
        <AucCard
          name="FHS (reference)"
          sub="Deterministic 6-subscore"
          auc={mc.fhs_reference.auc}
          note="the decider"
          accent="#3a4a42"
        />
      </div>

      {/* Agreement strip */}
      <div className="mb-6 grid grid-cols-2 gap-3 rounded-lg bg-ink/[0.03] p-4 sm:grid-cols-4">
        <Agree label="Champion ↔ Challenger" value={ag.champion_vs_challenger} highlight />
        <Agree label="All three agree" value={ag.all_three} />
        <Agree label="Champion ↔ FHS" value={ag.champion_vs_fhs} />
        <Agree label="PD rank corr." value={ag.pd_rank_corr_champ_chal} isCorr />
      </div>

      {/* Information Value ranking */}
      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <h3 className="font-display text-lg text-ink">Information Value — learned feature ranking</h3>
          <span className="text-[0.7rem] text-ink-faint">
            higher IV = stronger good/bad separation
          </span>
        </div>
        <p className="mb-3 text-sm text-ink-faint">
          The WOE bin cut-points are <span className="text-ink-soft">learned from the cohort default
          rate</span> — they replace the hand-set scoring ramps. Every feature is monotone.
        </p>
        <ul className="space-y-1.5">
          {mc.information_value_ranking.slice(0, 10).map((r) => (
            <li key={r.key} className="flex items-center gap-3 text-[0.82rem]">
              <span className="w-44 shrink-0 truncate text-ink-soft" title={r.label}>
                {r.label}
              </span>
              <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-paper-deep">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${(r.iv / maxIv) * 100}%`, background: "#2f6b50" }}
                />
              </div>
              <span className="w-12 shrink-0 text-right font-mono text-[0.72rem] text-ink">
                {r.iv.toFixed(2)}
              </span>
              <span
                className="w-16 shrink-0 text-right font-mono text-[0.6rem] uppercase tracking-wide"
                style={{ color: r.monotone ? "#2f6b50" : "#9e3b2e" }}
              >
                {r.monotone ? "mono ✓" : "non-mono"}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-5 space-y-1.5 rounded-lg bg-ink/[0.03] p-4 text-xs leading-relaxed text-ink-faint">
        {mc.notes.map((n, i) => (
          <p key={i}>· {n}</p>
        ))}
      </div>
    </section>
  );
}

function AucCard({
  name,
  sub,
  auc,
  note,
  accent,
}: {
  name: string;
  sub: string;
  auc: number;
  note: string;
  accent: string;
}) {
  return (
    <div className="rounded-lg border border-paper-line bg-paper-card px-4 py-3.5">
      <div className="flex items-baseline justify-between">
        <span className="font-display text-base text-ink">{name}</span>
        <span className="font-display text-2xl" style={{ color: accent }}>
          {auc.toFixed(3)}
        </span>
      </div>
      <div className="mt-0.5 text-[0.66rem] uppercase tracking-wide text-ink-faint">{sub}</div>
      <div className="mt-1.5 text-[0.7rem] text-ink-soft">AUC · {note}</div>
    </div>
  );
}

function Agree({
  label,
  value,
  highlight,
  isCorr,
}: {
  label: string;
  value: number;
  highlight?: boolean;
  isCorr?: boolean;
}) {
  return (
    <div>
      <div className="eyebrow text-ink-faint">{label}</div>
      <div
        className="mt-1 font-display text-2xl"
        style={{ color: highlight ? "#1f4d3a" : "#1c2b25" }}
      >
        {isCorr ? value.toFixed(2) : `${Math.round(value * 100)}%`}
      </div>
    </div>
  );
}
