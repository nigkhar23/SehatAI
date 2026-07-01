import type { Band, Decision } from "./types";

// Indian-numbering currency: ₹13,00,000 style.
export function inr(n: number): string {
  if (!n) return "₹0";
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export function inrLakh(n: number): string {
  if (!n) return "₹0";
  const l = n / 100000;
  return `₹${l % 1 === 0 ? l.toFixed(0) : l.toFixed(1)}L`;
}

export const SUBSCORE_LABELS: Record<string, string> = {
  cash_flow: "Cash-Flow Health",
  revenue_vitality: "Revenue Vitality",
  banking_discipline: "Banking Discipline",
  compliance: "Compliance & Formalization",
  leverage: "Leverage & Obligations",
  digital_footprint: "Digital Footprint",
};

export const SUBSCORE_SHORT: Record<string, string> = {
  cash_flow: "Cash-Flow",
  revenue_vitality: "Revenue",
  banking_discipline: "Discipline",
  compliance: "Compliance",
  leverage: "Leverage",
  digital_footprint: "Digital",
};

export const DECISION_LABEL: Record<Decision, string> = {
  approve: "Indicative Approve",
  refer: "Refer / Conditional",
  decline: "Decline",
};

export const DECISION_COLOR: Record<Decision, string> = {
  approve: "var(--approve)",
  refer: "var(--refer)",
  decline: "var(--decline)",
};

export const BAND_LABEL: Record<Band, string> = {
  AA: "AA · Prime",
  A: "A · Strong",
  B: "B · Watch",
  C: "C · Weak",
  D: "D · Distressed",
};

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
