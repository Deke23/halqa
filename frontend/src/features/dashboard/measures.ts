/**
 * The one place where the live endpoint and the simulation file are made to line up.
 *
 * Split keys now match (sex F and M, age bands 18-34, 35-49, 50-64 and 65+, nationality Cameroonian), so no key
 * translation is needed. What still differs:
 * - Live rates are {value, count, unit "share"}. Simulation rates are {value, numerator} with no unit.
 * - Live unresolved is {count, value (share), delay_reasons: list of {reason, n}}. Simulation unresolved is
 *   {count, rate, delay_reasons: object keyed by reason with a label}.
 * - Live and simulation use different delay-reason codes (live reads engine flags, simulation reads the step
 *   that was not reached in time), so each has its own label table in the locale file.
 * - `care_reached_rate` exists only in the simulation. The other measure names are identical.
 * - Teach-back, confidence, plan and re-engagement measures are not measured in the simulated baseline arm.
 * - The simulation endpoint ignores `split` and `region`; the page selects from the full file.
 */
import type { LiveMeasure, SimMeasure } from "./types";

export type MeasureKind = "time_h" | "time_d" | "rate" | "mean" | "unresolved";

export interface MeasureDef {
  name: string;
  kind: MeasureKind;
  /** Only in the simulation. */
  simOnly?: boolean;
}

export const MEASURES: MeasureDef[] = [
  { name: "time_to_notification_h", kind: "time_h" },
  { name: "time_to_acknowledgement_h", kind: "time_h" },
  { name: "time_to_confirmation_d", kind: "time_d" },
  { name: "time_to_consultation_d", kind: "time_d" },
  { name: "time_to_care_d", kind: "time_d" },
  { name: "referral_completion_rate", kind: "rate" },
  { name: "appointment_completion_rate", kind: "rate" },
  { name: "treatment_initiation_rate", kind: "rate" },
  { name: "care_reached_rate", kind: "rate", simOnly: true },
  { name: "unresolved_results", kind: "unresolved" },
  { name: "teach_back_pass_rate", kind: "rate" },
  { name: "patient_confidence_mean", kind: "mean" },
  { name: "plan_checkin_rate", kind: "rate" },
  { name: "re_engagement_after_lapse_rate", kind: "rate" },
];

export const RATE_MEASURES = [
  "referral_completion_rate",
  "appointment_completion_rate",
  "treatment_initiation_rate",
  "care_reached_rate",
];
export const DAY_MEASURES = ["time_to_confirmation_d", "time_to_consultation_d", "time_to_care_d"];

export interface Reason {
  key: string;
  n: number | null;
  suppressed: boolean;
}

/** Common shape for a live measure and a simulated one. */
export interface Norm {
  n: number;
  suppressed: boolean;
  median?: number | null;
  p90?: number | null;
  /** Rate, mean or share. */
  value?: number | null;
  count?: number | null;
  reasons?: Reason[];
}

export function normLive(m: LiveMeasure | undefined): Norm | undefined {
  if (!m) return undefined;
  return {
    n: m.n,
    suppressed: m.suppressed,
    median: m.median,
    p90: m.p90,
    value: m.value,
    count: m.count,
    reasons: m.delay_reasons?.map((r) => ({ key: r.reason, n: r.n, suppressed: r.suppressed })),
  };
}

export function normSim(m: SimMeasure | number | undefined): Norm | undefined {
  if (m === undefined || typeof m === "number") return undefined;
  return {
    n: m.n,
    suppressed: m.suppressed,
    median: m.median,
    p90: m.p90,
    value: m.value ?? m.rate,
    count: m.count ?? m.numerator,
    reasons: m.delay_reasons
      ? Object.entries(m.delay_reasons).map(([key, r]) => ({ key, n: r.count, suppressed: r.suppressed }))
      : undefined,
  };
}

/** Translation key for the group of a split, or null when the key is shown as it is. */
export function groupLabelKey(split: string, key: string): string | null {
  if (split === "language") return `language.${key}`;
  if (split === "sex") return `sex.${key}`;
  return null;
}
