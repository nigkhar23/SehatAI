// Shapes mirror the engine's Explanation payload (sehat/explain.py + api.py).

export type Decision = "approve" | "refer" | "decline";
export type Band = "AA" | "A" | "B" | "C" | "D";
export type Polarity = "strength" | "risk" | "neutral" | "gate";

export interface Reason {
  code: string;
  domain: string;
  polarity: Polarity;
  template: string;
  narration: string;
  grounded: boolean;
  used_llm: boolean;
}

export interface SubScore {
  name: string;
  value: number;
  available: boolean;
  weight: number;
  reweighted: boolean;
}

export interface Coverage {
  fraction: number;
  has_txns: boolean;
  has_gst: boolean;
  has_upi: boolean;
  epfo_applicable: boolean;
  txn_months: number;
  gst_returns: number;
  has_proxy?: boolean;
  proxy_type?: string | null;
}

// Operational proxy (electricity/water/fuel) — supplementary physical-activity
// signal for thin-file MSMEs. Present only on entities carrying a meter series.
export interface ProxyPoint {
  period: string;
  value: number;
}

export interface OperationalProxy {
  type: string; // "electricity" | "water" | "fuel"
  unit: string; // kWh / kL / L
  series: ProxyPoint[];
  trend_pct: number | null;
  recent_break_pct: number | null;
  recent_window_months: number;
}

export interface Entity {
  id: string;
  key: string;
  name: string;
  sector: string;
  state: string;
  reg_type: string;
  vintage_months: number;
  tagline: string;
}

export interface AuditInfo {
  input_hash: string;
  record_hash: string;
  scorecard_version: string;
  consent_id: string | null;
  blocking_gate: string | null;
  timestamp: string;
}

// --- Hybrid models (champion WOE scorecard + challenger monotone GBM + SHAP) ---
export interface ChampionContribution {
  key: string;
  label: string;
  domain: string;
  value: number | null;
  woe: number;
  points: number;
  missing: boolean;
}

export interface ChampionResult {
  pd: number;
  score_points: number;
  approve: boolean;
  threshold: number;
  contributions: ChampionContribution[];
  model_version: string;
}

export interface ShapContribution {
  key: string;
  label: string;
  domain: string;
  value: number | null;
  shap: number;
  direction: string;
}

export interface ChallengerResult {
  pd: number;
  base_value: number;
  approve: boolean;
  threshold: number;
  contributions: ShapContribution[];
  model_version: string;
}

export interface CrossCheckVerdict {
  fhs_approve: boolean | null;
  champion_approve: boolean | null;
  challenger_approve: boolean | null;
  agree: boolean;
  note: string;
}

export interface ModelCrossCheck {
  champion: ChampionResult | null;
  challenger: ChallengerResult | null;
  cross_check: CrossCheckVerdict;
  fhs_approve: boolean;
}

export interface Assessment {
  entity_id: string;
  fhs: number;
  band: Band;
  decision: Decision;
  blocking_gate: string | null;
  indicative_limit: number;
  post_loan_dscr: number | null;
  decision_summary: string;
  strengths: Reason[];
  risks: Reason[];
  notes: Reason[];
  gates: Reason[];
  narration_model_id: string;
  narration_prompt_version: string;
  narration_source: string;
  model_cross_check: ModelCrossCheck | null;
  entity: Entity;
  subscores: SubScore[];
  coverage: Coverage;
  operational_proxy?: OperationalProxy | null;
  bureau_thin_file: boolean;
  scorecard_version: string;
  audit: AuditInfo;
}

export interface PersonaListItem {
  id: string;
  key: string;
  name: string;
  sector: string;
  tagline: string;
  fhs: number;
  band: Band;
  decision: Decision;
  indicative_limit: number;
  thin_file: boolean;
}

export interface BandRow {
  band: Band;
  n: number;
  n_defaults: number;
  bad_rate: number;
  approve_rate_if_policy: number;
}

export interface GainsRow {
  decile: number;
  n: number;
  n_defaults: number;
  bad_rate: number;
  cum_defaults: number;
  cum_pct_defaults: number;
  lift: number;
}

export interface LiftResult {
  reject_cohort_n: number;
  sehat_approved_n: number;
  approval_rate: number;
  approved_bad_rate: number;
  declined_bad_rate: number;
  baseline_bad_rate: number;
  bad_rate_reduction_vs_blanket: number;
}

export interface ValidationReport {
  n: number;
  n_train: number;
  n_test: number;
  base_default_rate: number;
  auc: number;
  gini: number;
  ks: number;
  gains: GainsRow[];
  bands: BandRow[];
  lift: LiftResult;
  bad_rate_monotone: boolean;
  notes: string[];
}

// --- Segmentation (the unified score, cut by segment) ---
export interface SegmentStat {
  segment: string;
  n: number;
  n_defaults: number;
  bad_rate: number;
  approve_rate: number;
  band_counts: Record<string, number>;
}

export interface SegmentationReport {
  n_cohort: number;
  n_test: number;
  split_seed: number;
  test_size: number;
  overall: Omit<SegmentStat, "segment">;
  by_sector: SegmentStat[];
  by_state: SegmentStat[];
  by_reg_type: SegmentStat[];
  by_vintage_band: SegmentStat[];
  notes: string[];
}

// --- Model card (champion vs challenger vs FHS) ---
export interface IVRow {
  key: string;
  label: string;
  iv: number;
  monotone: boolean;
  n_bins: number;
}

export interface ModelCard {
  champion: {
    type: string;
    model_version: string;
    auc: number;
    approve_threshold_pd: number;
    n_features_shrunk_to_zero: number;
    coef_sign_constraint: string;
  };
  challenger: {
    type: string;
    auc: number;
    approve_threshold_pd: number;
    monotone_constraints: Record<string, number>;
    num_boost_round: number;
  };
  fhs_reference: { type: string; auc: number };
  agreement: {
    champion_vs_challenger: number;
    champion_vs_fhs: number;
    challenger_vs_fhs: number;
    all_three: number;
    pd_rank_corr_champ_chal: number;
  };
  information_value_ranking: IVRow[];
  n_train: number;
  n_test: number;
  base_default_rate: number;
  split_seed: number;
  notes: string[];
}
