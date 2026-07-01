"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { BandRow } from "@/lib/types";

const BAND_COLOR: Record<string, string> = {
  AA: "#1f4d3a",
  A: "#4f8a6e",
  B: "#b08433",
  C: "#c0703a",
  D: "#9e3b2e",
};

export default function BadRateChart({ bands }: { bands: BandRow[] }) {
  const data = bands.map((b) => ({
    band: b.band,
    bad: +(b.bad_rate * 100).toFixed(1),
    n: b.n,
  }));
  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 8, left: -8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#c9bca0" strokeOpacity={0.5} />
          <XAxis
            dataKey="band"
            tick={{ fill: "#3a4a42", fontSize: 12, fontFamily: "var(--font-mono)" }}
            axisLine={{ stroke: "#c9bca0" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#9aa89d", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            unit="%"
          />
          <Bar dataKey="bad" radius={[4, 4, 0, 0]} isAnimationActive animationDuration={900}>
            {data.map((d) => (
              <Cell key={d.band} fill={BAND_COLOR[d.band]} />
            ))}
            <LabelList
              dataKey="bad"
              position="top"
              formatter={(v: number) => `${v}%`}
              style={{ fill: "#3a4a42", fontSize: 11, fontFamily: "var(--font-mono)" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
