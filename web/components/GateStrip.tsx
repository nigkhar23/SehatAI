import type { Assessment, Reason } from "@/lib/types";

// Surfaces the pre-score gate verdicts (consent / fraud / bureau) as a status row.
// A blocking gate is highlighted in clay — this is the "necessary-but-insufficient"
// story that makes the score governable (e.g. great FHS but SMA-2 → decline).

function gateState(domain: string, reasons: Reason[], blocking: string | null) {
  const hit = reasons.find((r) => r.domain === domain);
  const isBlocking = blocking === domain;
  return { text: hit?.narration ?? "—", isBlocking, present: !!hit };
}

function Row({
  label,
  text,
  blocking,
}: {
  label: string;
  text: string;
  blocking: boolean;
}) {
  return (
    <div className="flex items-start gap-3 py-2">
      <span
        className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${
          blocking ? "bg-clay" : "bg-forest-mid"
        }`}
        aria-hidden
      />
      <div className="min-w-0">
        <span className="eyebrow mr-2 text-ink-faint">{label}</span>
        <span
          className={`text-[0.84rem] ${blocking ? "font-medium text-clay" : "text-ink-soft"}`}
        >
          {text}
        </span>
      </div>
    </div>
  );
}

export default function GateStrip({ assessment }: { assessment: Assessment }) {
  const all = assessment.gates;
  const consent = gateState("consent", all, assessment.blocking_gate);
  const fraud = gateState("fraud", all, assessment.blocking_gate);
  const bureau = gateState("bureau", all, assessment.blocking_gate);

  return (
    <div className="divide-y divide-paper-line/60">
      <Row label="Consent" text={consent.text} blocking={consent.isBlocking} />
      <Row label="Fraud / anti-gaming" text={fraud.text} blocking={fraud.isBlocking} />
      <Row label="Bureau hard-gate" text={bureau.text} blocking={bureau.isBlocking} />
    </div>
  );
}
