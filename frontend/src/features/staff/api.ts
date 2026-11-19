/** Typed query and mutation hooks for the staff screens. Cache keys come from the shared qk so the demo bar refreshes them. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { qk } from "@/api/hooks";
import { useAuth } from "@/api/auth";
import type {
  Action,
  CaseDetail,
  CaseList,
  Channel,
  DraftOut,
  EConsult,
  IntakeResponse,
  Language,
  MessageOut,
  UserOut,
} from "./types";

/** All cases the caller may see, sorted urgent first then most overdue. Queue tabs are filtered from this list. */
export function useCaseList(region: string) {
  return useQuery<CaseList>({
    queryKey: qk.caseList("all", region),
    queryFn: () => api<CaseList>("/cases", { query: { queue: "all", region } }),
    refetchInterval: 15_000,
  });
}

export function useStaffCase(id: string | undefined) {
  return useQuery<CaseDetail>({
    queryKey: qk.caseDetail(id ?? ""),
    queryFn: () => api<CaseDetail>(`/cases/${id}`),
    enabled: !!id,
  });
}

export function useStaffUsers() {
  return useQuery<UserOut[]>({ queryKey: ["staff", "users"], queryFn: () => api<UserOut[]>("/users"), staleTime: 60_000 });
}

export function useMyEconsults(enabled = true) {
  return useQuery<EConsult[]>({
    queryKey: ["cases", "econsults", "mine"],
    queryFn: () => api<EConsult[]>("/econsults"),
    enabled,
    refetchInterval: 15_000,
  });
}

/** Posts one action. The returned detail replaces the cached case, then every case and dashboard query refreshes. */
export function useStaffAction(caseId: string | undefined) {
  const qc = useQueryClient();
  return useMutation<CaseDetail, unknown, { action: Action; payload?: Record<string, unknown> }>({
    mutationFn: (body) => api<CaseDetail>(`/cases/${caseId}/actions`, { method: "POST", body }),
    onSuccess: (data) => {
      if (caseId) qc.setQueryData(qk.caseDetail(caseId), data);
      void qc.invalidateQueries({ queryKey: qk.cases });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useAskEconsult(caseId: string | undefined) {
  const qc = useQueryClient();
  return useMutation<EConsult, unknown, { to_user_id: number; question: string }>({
    mutationFn: (body) => api<EConsult>(`/cases/${caseId}/econsults`, { method: "POST", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.cases }),
  });
}

export function useAnswerEconsult() {
  const qc = useQueryClient();
  return useMutation<EConsult, unknown, { econsultId: number; answer: string }>({
    mutationFn: ({ econsultId, answer }) => api<EConsult>(`/econsults/${econsultId}/reply`, { method: "POST", body: { answer } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.cases }),
  });
}

export function useDraft(caseId: string | undefined) {
  return useMutation<DraftOut, unknown, { template_id: string; language: Language; tone?: string | null; channel?: Channel | null }>({
    mutationFn: (body) => api<DraftOut>(`/cases/${caseId}/messages/draft`, { method: "POST", body }),
  });
}

export function useSendDraft(caseId: string | undefined) {
  const qc = useQueryClient();
  return useMutation<{ message: MessageOut }, unknown, { draft_id: number; approve: boolean }>({
    mutationFn: (body) => api<{ message: MessageOut }>(`/cases/${caseId}/messages/send`, { method: "POST", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.cases }),
  });
}

export interface SimulatedReading {
  systolic: number;
  diastolic: number;
}

/** Simulated source feed. A fresh patient reference per click, because a patient with an open case never gets a second one. */
export function useSimulateResult() {
  const qc = useQueryClient();
  return useMutation<IntakeResponse, unknown, { region: "AUH" | "YDE"; reading: SimulatedReading }>({
    mutationFn: ({ region, reading }) =>
      api<IntakeResponse>("/intake/result", {
        method: "POST",
        body: {
          patient_ref: `SIM-${reading.systolic}-${Date.now().toString(36).slice(-4).toUpperCase()}`,
          source_system: region === "AUH" ? "IFHAS_SCREENING" : "CLINIC_READING",
          region,
          readings: [{ systolic: reading.systolic, diastolic: reading.diastolic }],
        },
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.cases }),
  });
}

export function useFhirBundle(caseId: string | undefined, enabled: boolean) {
  return useQuery<Record<string, unknown>>({
    queryKey: qk.fhir(caseId ?? ""),
    queryFn: () => api<Record<string, unknown>>(`/cases/${caseId}/fhir`),
    enabled: !!caseId && enabled,
  });
}

/** The signed-in staff member's numeric id. The shared auth type is loose, the server sends a number. */
export function useMyUserId(): number | undefined {
  const { user } = useAuth();
  return user ? Number(user.id) : undefined;
}
