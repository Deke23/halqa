import type { components } from "@/api/schema";

type S = components["schemas"];

export type LiveResponse = S["DashboardLive"];
export type LiveMeasure = S["Measure"];
export type Split = S["Split"];
export type RegionKey = "AUH" | "YDE";
export type Arm = "baseline" | "with_loop";

export const SPLITS: Split[] = ["none", "language", "nationality_group", "sex", "age_band"];

/** One measure inside one simulation cell. Fields differ by measure kind, so all are optional. */
export interface SimMeasure {
  n: number;
  suppressed: boolean;
  median?: number | null;
  p90?: number | null;
  unit?: string;
  value?: number | null;
  numerator?: number;
  count?: number | null;
  rate?: number | null;
  note?: string;
  delay_reasons?: Record<string, { label: string; count: number | null; suppressed: boolean }>;
}

export type SimCell = { n_actionable: number } & Record<string, SimMeasure | number>;

export interface SimParam {
  name: string;
  arm: string;
  parameter: string;
  value: unknown;
  unit: string;
  source: string;
  kind: "published" | "assumption";
  rationale?: string;
}

export interface SimSensitivityRun {
  baseline_care_reached_rate: number;
  with_loop_care_reached_rate: number;
  difference: number;
}

export interface SimSensitivityTop {
  parameter: string;
  base_value: number;
  low_value: number;
  high_value: number;
  low: SimSensitivityRun;
  base: SimSensitivityRun;
  high: SimSensitivityRun;
}

export interface SimResponse {
  available: boolean;
  metadata?: {
    disclaimer: string;
    cohort_size_per_region: number;
    cohort_summary: Record<RegionKey, { people: number; actionable: number; severe: number }>;
    min_cell_size: number;
    generated_at: string;
  };
  published_sources?: Record<string, string>;
  parameters?: SimParam[];
  results?: Record<RegionKey, Record<Arm, Record<string, Record<string, SimCell>>>>;
  sensitivity?: Record<
    RegionKey,
    {
      outcome: string;
      method: string;
      ranking_top10: Array<{ parameter: string; swing_in_care_rate_difference: number }>;
      top3: SimSensitivityTop[];
    }
  >;
}
