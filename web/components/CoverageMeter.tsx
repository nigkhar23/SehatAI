import type { Coverage } from "@/lib/types";
import { titleCase } from "@/lib/format";

function Pill({ label, state }: { label: string; state: "yes" | "no" | "na" }) {
  const style =
    state === "yes"
      ? "border-forest/30 bg-forest/5 text-forest"
      : state === "na"
        ? "border-paper-line bg-paper text-ink-faint"
        : "border-clay/30 bg-clay/5 text-clay";
  const mark = state === "yes" ? "✓" : state === "na" ? "—" : "✕";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium ${style}`}
    >
      <span aria-hidden>{mark}</span>
      {label}
    </span>
  );
}

export default function CoverageMeter({ coverage }: { coverage: Coverage }) {
  const pct = Math.round(coverage.fraction * 100);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="eyebrow text-ink-faint">Data Coverage</span>
        <span className="font-mono text-sm text-ink-soft">{pct}%</span>
      </div>
      <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-paper-deep">
        <div
          className="h-full rounded-full bg-forest-mid transition-[width] duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Pill
          label={`Bank txns${coverage.has_txns ? ` · ${coverage.txn_months}mo` : ""}`}
          state={coverage.has_txns ? "yes" : "no"}
        />
        <Pill
          label={`GST${coverage.has_gst ? ` · ${coverage.gst_returns}` : ""}`}
          state={coverage.has_gst ? "yes" : "no"}
        />
        <Pill label="UPI" state={coverage.has_upi ? "yes" : "no"} />
        <Pill
          label={coverage.epfo_applicable ? "EPFO" : "EPFO · n/a (micro)"}
          state={coverage.epfo_applicable ? "yes" : "na"}
        />
        {coverage.has_proxy && (
          <Pill
            label={`${titleCase(coverage.proxy_type ?? "proxy")} proxy`}
            state="yes"
          />
        )}
      </div>
    </div>
  );
}
