// Static data layer. The demo reads bundled engine snapshots (web/lib/data/*.json)
// so the deployed card has ZERO backend dependency. If NEXT_PUBLIC_API_BASE is set,
// pages can optionally re-fetch from the live FastAPI engine at runtime.

import type {
  Assessment,
  ModelCard,
  PersonaListItem,
  SegmentationReport,
  ValidationReport,
} from "./types";
// PersonaListItem is used by getPersonas; PortfolioRow (below) types the trimmed
// rows the /portfolio endpoint returns.

import personasJson from "./data/personas.json";
import portfolioJson from "./data/portfolio.json";
import validationJson from "./data/validation.json";

import P1 from "./data/assess/P1_STRONG.json";
import P2 from "./data/assess/P2_HERO.json";
import P3 from "./data/assess/P3_BORDERLINE.json";
import P4 from "./data/assess/P4_DECLINE.json";
import P5 from "./data/assess/P5_DELINQUENT.json";
import P6 from "./data/assess/P6_FRAUD_PARTIAL.json";
import P7 from "./data/assess/P7_PROXY_MFG.json";
import P7B from "./data/assess/P7B_PROXY_SLOWDOWN.json";

const ASSESSMENTS: Record<string, Assessment> = {
  P1_STRONG: P1 as unknown as Assessment,
  P2_HERO: P2 as unknown as Assessment,
  P3_BORDERLINE: P3 as unknown as Assessment,
  P4_DECLINE: P4 as unknown as Assessment,
  P5_DELINQUENT: P5 as unknown as Assessment,
  P6_FRAUD_PARTIAL: P6 as unknown as Assessment,
  P7_PROXY_MFG: P7 as unknown as Assessment,
  P7B_PROXY_SLOWDOWN: P7B as unknown as Assessment,
};

export function getPersonas(): PersonaListItem[] {
  return (personasJson as { personas: PersonaListItem[] }).personas;
}

export function getPersonaIds(): string[] {
  return getPersonas().map((p) => p.id);
}

export function getAssessment(id: string): Assessment | null {
  return ASSESSMENTS[id] ?? null;
}

export function getValidation(): ValidationReport {
  return (validationJson as { report: ValidationReport }).report;
}

// The hybrid model card (champion vs challenger vs FHS). Embedded in the validation
// snapshot; null if the models haven't been trained/frozen yet (page degrades).
export function getModelCard(): ModelCard | null {
  return (validationJson as { model_card?: ModelCard }).model_card ?? null;
}

export interface PortfolioRow {
  id: string;
  name: string;
  sector: string;
  fhs: number;
  band: string;
  decision: string;
  indicative_limit: number;
  thin_file: boolean;
}

export function getPortfolio() {
  return portfolioJson as {
    demo_book: {
      personas: PortfolioRow[];
      decision_counts: Record<string, number>;
      total_indicative_exposure: number;
    };
    cohort: {
      n_test: number;
      base_default_rate: number;
      auc: number;
      ks: number;
      gini: number;
      bands: ValidationReport["bands"];
      lift: ValidationReport["lift"];
      bad_rate_monotone: boolean;
    };
    segmentation: SegmentationReport | null;
    scorecard_version: string;
  };
}

export const SCORECARD_VERSION =
  (personasJson as { scorecard_version: string }).scorecard_version;
