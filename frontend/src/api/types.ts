/**
 * Loose types for the first version of the front end.
 *
 * Swapping in generated types: run `npm run gen:api` once docs/openapi.json exists.
 * That writes src/api/schema.d.ts. Then, for each alias below, replace the loose type with
 *   import type { components } from "./schema";
 *   export type CaseDetail = components["schemas"]["CaseDetail"];
 * The hooks in hooks.ts only import types from this file, so nothing else changes.
 */
export type Persona =
  | "patient_auh"
  | "coordinator_auh"
  | "clinician_pcp"
  | "clinician_specialist"
  | "patient_yde"
  | "nurse_yde"
  | "analyst";

export const PERSONAS: readonly Persona[] = [
  "patient_auh",
  "coordinator_auh",
  "clinician_pcp",
  "clinician_specialist",
  "patient_yde",
  "nurse_yde",
  "analyst",
];

export type Role = "patient" | "coordinator" | "clinician" | "analyst";

export type CaseState =
  | "RESULT_ISSUED"
  | "NOTIFIED"
  | "ACKNOWLEDGED"
  | "CONFIRMED"
  | "REFERRED"
  | "APPOINTMENT_BOOKED"
  | "IN_CARE"
  | "CLOSED";

export const CASE_STATES: readonly CaseState[] = [
  "RESULT_ISSUED",
  "NOTIFIED",
  "ACKNOWLEDGED",
  "CONFIRMED",
  "REFERRED",
  "APPOINTMENT_BOOKED",
  "IN_CARE",
  "CLOSED",
];

export type OwnerRole =
  | "coordinator"
  | "primary_care_clinician"
  | "receiving_clinician"
  | "treating_clinician"
  | "clinician"
  | "patient"
  | "none";

export type QueueName = "all" | "urgent" | "overdue" | "rejected" | "unowned" | "escalated" | "mine";

export type CaseActionName =
  | "notify"
  | "acknowledge"
  | "choose_confirmation"
  | "add_reading"
  | "review_confirmation"
  | "refer"
  | "accept_referral"
  | "reject_referral"
  | "assign_owner"
  | "book_appointment"
  | "record_visit"
  | "plan_checkin"
  | "escalate"
  | "close"
  | "reopen"
  | "update_consent";

export interface User {
  id: string;
  name: string;
  role: Role;
  persona?: Persona;
  region?: string;
  language?: string;
  [key: string]: unknown;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface Owner {
  user_id?: string | null;
  name?: string | null;
  role?: OwnerRole | null;
}

export interface NextStep {
  label_key?: string;
  owner?: Owner | null;
  owner_role?: OwnerRole | null;
  due_at?: string | null;
  overdue?: boolean;
  escalation_level?: number;
  [key: string]: unknown;
}

/** Summary row in a queue. The backend owns exact fields; extra fields pass through. */
export interface CaseSummary {
  id: string;
  state: CaseState;
  urgent?: boolean;
  patient_initials?: string;
  next_step?: NextStep;
  reason?: string | null;
  [key: string]: unknown;
}

export interface JourneyStepData {
  state: CaseState;
  done_at?: string | null;
  current?: boolean;
}

export interface TimelineEvent {
  id: string | number;
  at: string;
  type: string;
  actor_role?: string | null;
  actor_user_id?: string | null;
  actor_name?: string | null;
  from_state?: CaseState | null;
  to_state?: CaseState | null;
  reason?: string | null;
  payload?: unknown;
}

export interface CaseDetail extends CaseSummary {
  allowed_actions?: CaseActionName[];
  timeline?: TimelineEvent[];
  progress?: JourneyStepData[];
  readings?: unknown[];
}

export interface DemoClock {
  now: string;
  offset_hours?: number;
  [key: string]: unknown;
}

export interface CaseActionBody {
  action: CaseActionName;
  payload?: Record<string, unknown>;
}

export type ConfigResponse = Record<string, unknown>;
export type DashboardResponse = Record<string, unknown>;
export type FhirBundle = Record<string, unknown>;
export type Message = Record<string, unknown> & { id?: string | number };
export type Slot = Record<string, unknown> & { id: string };
export interface Draft {
  text: string;
  source: "TEMPLATE" | "AI_REWORDED";
  template_id: string;
  template_version?: string | number;
  validation?: unknown;
}
