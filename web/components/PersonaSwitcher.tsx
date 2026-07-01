"use client";

import Link from "next/link";
import type { PersonaListItem } from "@/lib/types";

const DEC_DOT: Record<string, string> = {
  approve: "#2f6b50",
  refer: "#b08433",
  decline: "#9e3b2e",
};

export default function PersonaSwitcher({
  personas,
  activeId,
}: {
  personas: PersonaListItem[];
  activeId: string;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {personas.map((p, i) => {
        const active = p.id === activeId;
        return (
          <Link
            key={p.id}
            href={`/card/${p.id}/`}
            scroll={false}
            className={`group relative rounded-lg border px-3 py-2 text-left transition-all ${
              active
                ? "border-forest/50 bg-forest/[0.06] shadow-inset"
                : "border-paper-line bg-paper-card hover:border-brass/50 hover:bg-paper"
            }`}
          >
            <div className="flex items-center gap-2">
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: DEC_DOT[p.decision] }}
              />
              <span className="font-mono text-[0.62rem] text-ink-faint">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span
                className={`text-[0.82rem] font-medium ${
                  active ? "text-forest-deep" : "text-ink-soft"
                }`}
              >
                {p.name}
              </span>
            </div>
            {p.thin_file && (
              <span className="mt-1 inline-block rounded bg-brass/10 px-1.5 py-0.5 font-mono text-[0.56rem] uppercase tracking-wider text-brass-deep">
                credit-invisible
              </span>
            )}
          </Link>
        );
      })}
    </div>
  );
}
