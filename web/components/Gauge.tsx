"use client";

import { useEffect, useState } from "react";
import type { Band } from "@/lib/types";

/**
 * The FHS dial — a hand-drawn measuring instrument. A 240° arc with etched band
 * ticks (D→AA), a sweeping needle, and the score set in the display serif. This
 * is the card's signature object; it should read as a calibrated gauge, not a
 * generic progress ring.
 */

const START = 150; // degrees (bottom-left)
const SWEEP = 240; // total arc

// Band thresholds on the 0-100 scale (lower bound of each band).
const BANDS: { band: Band; from: number; to: number; color: string }[] = [
  { band: "D", from: 0, to: 40, color: "#9e3b2e" },
  { band: "C", from: 40, to: 55, color: "#c0703a" },
  { band: "B", from: 55, to: 70, color: "#b08433" },
  { band: "A", from: 70, to: 85, color: "#4f8a6e" },
  { band: "AA", from: 85, to: 100, color: "#1f4d3a" },
];

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, r: number, a0: number, a1: number) {
  const p0 = polar(cx, cy, r, a0);
  const p1 = polar(cx, cy, r, a1);
  const large = a1 - a0 > 180 ? 1 : 0;
  return `M ${p0.x} ${p0.y} A ${r} ${r} 0 ${large} 1 ${p1.x} ${p1.y}`;
}

export default function Gauge({
  value,
  band,
  size = 280,
}: {
  value: number;
  band: Band;
  size?: number;
}) {
  // The score is rendered CORRECTLY from the first paint — never count up from 0
  // (a credit score must not flash a wrong number). Only the needle sweeps in, via
  // the CSS transition below; the numeral is always the true value.
  const [needleReady, setNeedleReady] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setNeedleReady(true));
    return () => cancelAnimationFrame(id);
  }, []);
  const shown = value;
  const sweepValue = needleReady ? value : 0;

  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 26;
  const needleAngle = START + (Math.min(100, Math.max(0, sweepValue)) / 100) * SWEEP;
  const needle = polar(cx, cy, r - 14, needleAngle);
  const bandColor = BANDS.find((b) => b.band === band)?.color ?? "#1f4d3a";

  // Major ticks every 10 units.
  const ticks = Array.from({ length: 11 }, (_, i) => i * 10);

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Band arcs */}
        {BANDS.map((b) => {
          const a0 = START + (b.from / 100) * SWEEP;
          const a1 = START + (b.to / 100) * SWEEP;
          return (
            <path
              key={b.band}
              d={arcPath(cx, cy, r, a0, a1)}
              fill="none"
              stroke={b.color}
              strokeWidth={9}
              strokeLinecap="butt"
              opacity={band === b.band ? 0.95 : 0.28}
            />
          );
        })}

        {/* Etched tick marks + labels */}
        {ticks.map((t) => {
          const a = START + (t / 100) * SWEEP;
          const outer = polar(cx, cy, r - 16, a);
          const inner = polar(cx, cy, r - (t % 20 === 0 ? 27 : 22), a);
          const label = polar(cx, cy, r - 40, a);
          return (
            <g key={t}>
              <line
                x1={outer.x}
                y1={outer.y}
                x2={inner.x}
                y2={inner.y}
                stroke="#1c2b25"
                strokeWidth={t % 20 === 0 ? 1.4 : 0.8}
                opacity={0.5}
              />
              {t % 20 === 0 && (
                <text
                  x={label.x}
                  y={label.y}
                  fill="#6b7a70"
                  fontSize={9}
                  fontFamily="var(--font-mono)"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {t}
                </text>
              )}
            </g>
          );
        })}

        {/* Needle */}
        <line
          x1={cx}
          y1={cy}
          x2={needle.x}
          y2={needle.y}
          stroke={bandColor}
          strokeWidth={2.5}
          strokeLinecap="round"
          style={{ transition: "all 1.1s cubic-bezier(0.2,0.7,0.2,1)" }}
        />
        <circle cx={cx} cy={cy} r={6} fill="#fbf8f0" stroke={bandColor} strokeWidth={2} />
        <circle cx={cx} cy={cy} r={2} fill={bandColor} />
      </svg>

      {/* Centre readout */}
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pb-6">
        <div
          className="font-display leading-none tabular-nums"
          style={{ fontSize: size * 0.26, color: bandColor, fontWeight: 600 }}
        >
          {shown.toFixed(0)}
        </div>
        <div className="eyebrow mt-1 text-ink-faint">Health Score</div>
      </div>
    </div>
  );
}
