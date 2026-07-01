"use client";

import { useState } from "react";
import type { Assessment } from "@/lib/types";

// "Why this decision" — exposes the deterministic trail: gate verdicts, the
// machine reason codes, and the audit hashes. The judge-facing proof that the
// LLM narrates but never decides.
export default function WhyDrawer({ assessment }: { assessment: Assessment }) {
  const [open, setOpen] = useState(false);
  const a = assessment;

  return (
    <div className="rounded-xl border border-paper-line bg-paper-card/60">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-5 py-3.5 text-left"
      >
        <span className="eyebrow text-ink-soft">Why this decision — the audit trail</span>
        <span
          className="font-mono text-lg text-brass transition-transform"
          style={{ transform: open ? "rotate(45deg)" : "none" }}
          aria-hidden
        >
          +
        </span>
      </button>

      {open && (
        <div className="rise space-y-4 border-t border-paper-line px-5 py-4">
          <p className="text-sm leading-relaxed text-ink-soft">{a.decision_summary}</p>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <div className="eyebrow mb-1.5 text-ink-faint">Decision rule fired</div>
              <code className="block rounded bg-paper px-2.5 py-1.5 font-mono text-xs text-ink">
                {a.blocking_gate
                  ? `hard-gate → ${a.blocking_gate}`
                  : `band policy → ${a.band}`}
              </code>
            </div>
            <div>
              <div className="eyebrow mb-1.5 text-ink-faint">Indicative limit</div>
              <code className="block rounded bg-paper px-2.5 py-1.5 font-mono text-xs text-ink">
                {a.indicative_limit > 0
                  ? `₹${a.indicative_limit.toLocaleString("en-IN")} · post-loan DSCR ${a.post_loan_dscr ?? "—"}`
                  : "— (not approved)"}
              </code>
            </div>
          </div>

          <div>
            <div className="eyebrow mb-1.5 text-ink-faint">
              Machine reason codes (the LLM only rephrases these)
            </div>
            <div className="flex flex-wrap gap-1.5">
              {[...a.strengths, ...a.risks, ...a.notes, ...a.gates].map((r) => (
                <code
                  key={r.code}
                  className="rounded bg-paper px-2 py-0.5 font-mono text-[0.6rem] text-ink-soft"
                >
                  {r.code}
                </code>
              ))}
            </div>
          </div>

          <div className="grid gap-3 rounded-lg bg-ink/[0.03] p-3 sm:grid-cols-2">
            <KV label="Scorecard version" value={a.scorecard_version} />
            <KV label="Consent ID" value={a.audit.consent_id ?? "—"} />
            <KV label="Input hash" value={a.audit.input_hash.slice(0, 24) + "…"} />
            <KV label="Record hash" value={a.audit.record_hash} />
            <KV
              label="Narration model"
              value={`${a.narration_model_id} · ${a.narration_prompt_version}`}
            />
            <KV label="Narration source" value={a.narration_source} />
          </div>
          <p className="text-[0.7rem] leading-relaxed text-ink-faint">
            Every number shown on this card is emitted by the deterministic engine and
            grounding-validated. The card makes zero live LLM calls — narration is
            pre-generated offline and re-checked against the computed values at render.
          </p>
        </div>
      )}
    </div>
  );
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="eyebrow text-ink-faint">{label}</div>
      <div className="truncate font-mono text-[0.7rem] text-ink-soft">{value}</div>
    </div>
  );
}
