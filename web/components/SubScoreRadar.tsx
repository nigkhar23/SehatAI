"use client";

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";
import type { SubScore } from "@/lib/types";
import { SUBSCORE_SHORT } from "@/lib/format";

export default function SubScoreRadar({ subscores }: { subscores: SubScore[] }) {
  const data = subscores.map((s) => ({
    axis: SUBSCORE_SHORT[s.name] ?? s.name,
    value: s.available ? s.value : 0,
    weight: Math.round(s.weight * 100),
  }));

  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="#c9bca0" strokeOpacity={0.7} />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fill: "#3a4a42", fontSize: 11, fontFamily: "var(--font-archivo)" }}
          />
          <PolarRadiusAxis
            domain={[0, 100]}
            tick={{ fill: "#9aa89d", fontSize: 8 }}
            axisLine={false}
            tickCount={5}
          />
          <Radar
            dataKey="value"
            stroke="#1f4d3a"
            strokeWidth={2}
            fill="#2f6b50"
            fillOpacity={0.22}
            isAnimationActive
            animationDuration={900}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
