import type { Language } from "@/config";
import type { Persona, Role } from "@/api/types";

export interface PersonaMeta {
  key: Persona;
  role: Role;
  /** Region key, matches the regions.* strings. "all" for the analyst. */
  region: "abu_dhabi" | "yaounde" | "all";
  /** Where this persona lands after sign in. */
  home: string;
  /** Language the UI switches to on sign in. The user can change it afterwards. */
  language: Language;
}

export const PERSONA_META: Record<Persona, PersonaMeta> = {
  patient_auh: { key: "patient_auh", role: "patient", region: "abu_dhabi", home: "/patient", language: "ar" },
  coordinator_auh: { key: "coordinator_auh", role: "coordinator", region: "abu_dhabi", home: "/staff/queue", language: "en" },
  clinician_pcp: { key: "clinician_pcp", role: "clinician", region: "abu_dhabi", home: "/staff/worklist", language: "en" },
  clinician_specialist: { key: "clinician_specialist", role: "clinician", region: "abu_dhabi", home: "/staff/worklist", language: "en" },
  patient_yde: { key: "patient_yde", role: "patient", region: "yaounde", home: "/phone", language: "fr" },
  nurse_yde: { key: "nurse_yde", role: "coordinator", region: "yaounde", home: "/staff/queue", language: "fr" },
  analyst: { key: "analyst", role: "analyst", region: "all", home: "/dashboard", language: "en" },
};

export function homeFor(persona: Persona | null | undefined, role?: Role): string {
  if (persona && PERSONA_META[persona]) return PERSONA_META[persona].home;
  switch (role) {
    case "patient":
      return "/patient";
    case "coordinator":
      return "/staff/queue";
    case "clinician":
      return "/staff/worklist";
    case "analyst":
      return "/dashboard";
    default:
      return "/";
  }
}
