/**
 * TanStack Query hooks for the routes in SPEC section 6.
 *
 * Types are loose for now (see types.ts). Every hook takes an optional type argument, so a feature
 * can write useCase<MyCaseDetail>(id) today. After `npm run gen:api` has produced schema.d.ts,
 * change the aliases in types.ts to the generated schemas and the defaults here follow.
 */
import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from "@tanstack/react-query";
import { api } from "./client";
import { useAuth } from "./auth";
import type {
  CaseActionBody,
  CaseDetail,
  CaseSummary,
  ConfigResponse,
  DashboardResponse,
  DemoClock,
  Draft,
  FhirBundle,
  Message,
  QueueName,
  Slot,
  User,
} from "./types";

export const qk = {
  me: ["me"] as const,
  config: ["config"] as const,
  cases: ["cases"] as const,
  caseList: (queue: string, region: string) => ["cases", "list", queue, region] as const,
  caseDetail: (id: string) => ["cases", "detail", id] as const,
  myCase: ["cases", "mine"] as const,
  slots: (id: string) => ["cases", "slots", id] as const,
  fhir: (id: string) => ["cases", "fhir", id] as const,
  myMessages: ["my", "messages"] as const,
  dashboardLive: (split: string, region: string) => ["dashboard", "live", split, region] as const,
  dashboardSim: (split: string) => ["dashboard", "simulation", split] as const,
  clock: ["demo", "clock"] as const,
};

type Opts<T> = Omit<UseQueryOptions<T>, "queryKey" | "queryFn">;

// ---- Identity and public config -------------------------------------------------------

export function useMe<T = User>(opts?: Opts<T>) {
  const { isSignedIn } = useAuth();
  return useQuery<T>({ queryKey: qk.me, queryFn: () => api<T>("/me"), enabled: isSignedIn, ...opts });
}

/** Public: thresholds, service levels, closure evidence types, template catalogue, languages. */
export function useConfig<T = ConfigResponse>(opts?: Opts<T>) {
  return useQuery<T>({
    queryKey: qk.config,
    queryFn: () => api<T>("/config", { anonymous: true }),
    staleTime: 5 * 60_000,
    ...opts,
  });
}

// ---- Cases ----------------------------------------------------------------------------

/** Staff only. The backend sorts urgent first, then most overdue. */
export function useCases<T = CaseSummary[]>(queue: QueueName = "all", region = "", opts?: Opts<T>) {
  return useQuery<T>({
    queryKey: qk.caseList(queue, region),
    queryFn: () => api<T>("/cases", { query: { queue, region } }),
    ...opts,
  });
}

export function useCase<T = CaseDetail>(caseId: string | undefined, opts?: Opts<T>) {
  return useQuery<T>({
    queryKey: qk.caseDetail(caseId ?? ""),
    queryFn: () => api<T>(`/cases/${caseId}`),
    enabled: !!caseId,
    ...opts,
  });
}

/** Patient shortcut: the signed-in patient's own case (patient-safe projection). */
export function useMyCase<T = CaseDetail>(opts?: Opts<T>) {
  return useQuery<T>({ queryKey: qk.myCase, queryFn: () => api<T>("/my/case"), ...opts });
}

export function useSlots<T = Slot[]>(caseId: string | undefined, opts?: Opts<T>) {
  return useQuery<T>({
    queryKey: qk.slots(caseId ?? ""),
    queryFn: () => api<T>(`/cases/${caseId}/slots`),
    enabled: !!caseId,
    ...opts,
  });
}

/** FHIR R4 Bundle for the JSON drawer. Enable it only when the drawer is open. */
export function useFhir<T = FhirBundle>(caseId: string | undefined, enabled = true, opts?: Opts<T>) {
  return useQuery<T>({
    queryKey: qk.fhir(caseId ?? ""),
    queryFn: () => api<T>(`/cases/${caseId}/fhir`),
    enabled: !!caseId && enabled,
    ...opts,
  });
}

/**
 * The only way to change case state. Posts {action, payload}, then refreshes every case query
 * (lists, detail, patient shortcut, slots). On failure the mutation error is a normalised
 * ApiError: 403 role not allowed, 409 state does not allow it, 422 bad payload.
 */
export function useCaseAction<TResult = CaseDetail>(caseId: string | undefined) {
  const qc = useQueryClient();
  return useMutation<TResult, unknown, CaseActionBody>({
    mutationFn: (body) => api<TResult>(`/cases/${caseId}/actions`, { method: "POST", body }),
    onSuccess: (data) => {
      if (caseId) qc.setQueryData(qk.caseDetail(caseId), data);
      void qc.invalidateQueries({ queryKey: qk.cases });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
      void qc.invalidateQueries({ queryKey: qk.myMessages });
    },
  });
}

export function useCreateEconsult(caseId: string | undefined) {
  const qc = useQueryClient();
  return useMutation<unknown, unknown, { to_user_id: string; question: string }>({
    mutationFn: (body) => api(`/cases/${caseId}/econsults`, { method: "POST", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.cases }),
  });
}

export function useReplyEconsult() {
  const qc = useQueryClient();
  return useMutation<unknown, unknown, { econsultId: string; answer: string }>({
    mutationFn: ({ econsultId, answer }) =>
      api(`/econsults/${econsultId}/reply`, { method: "POST", body: { answer } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.cases }),
  });
}

// ---- Messages -------------------------------------------------------------------------

export function useDraftMessage(caseId: string | undefined) {
  return useMutation<Draft, unknown, { template_id: string; language: string; tone?: string }>({
    mutationFn: (body) => api<Draft>(`/cases/${caseId}/messages/draft`, { method: "POST", body }),
  });
}

export function useSendMessage(caseId: string | undefined) {
  const qc = useQueryClient();
  return useMutation<unknown, unknown, { draft: Draft | Record<string, unknown> }>({
    mutationFn: (body) => api(`/cases/${caseId}/messages/send`, { method: "POST", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.cases });
      void qc.invalidateQueries({ queryKey: qk.myMessages });
    },
  });
}

/** Phone thread for the signed-in patient. Poll so replies from the engine show up. */
export function useMyMessages<T = Message[]>(opts?: Opts<T>) {
  return useQuery<T>({ queryKey: qk.myMessages, queryFn: () => api<T>("/my/messages"), refetchInterval: 4000, ...opts });
}

/** Keyword replies only (for example "1" or "2"). Parsed by fixed rules on the server. */
export function useReplyMessage() {
  const qc = useQueryClient();
  return useMutation<unknown, unknown, { text: string }>({
    mutationFn: (body) => api("/my/messages/reply", { method: "POST", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.myMessages });
      void qc.invalidateQueries({ queryKey: qk.cases });
    },
  });
}

// ---- Intake and dashboard -------------------------------------------------------------

/** The "Simulate incoming severe result" button posts here. */
export function useIntakeResult() {
  const qc = useQueryClient();
  return useMutation<unknown, unknown, Record<string, unknown>>({
    mutationFn: (body) => api("/intake/result", { method: "POST", body }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.cases }),
  });
}

export function useDashboardLive<T = DashboardResponse>(split = "none", region = "", opts?: Opts<T>) {
  return useQuery<T>({
    queryKey: qk.dashboardLive(split, region),
    queryFn: () => api<T>("/dashboard/live", { query: { split, region } }),
    ...opts,
  });
}

export function useDashboardSimulation<T = DashboardResponse>(split = "none", opts?: Opts<T>) {
  return useQuery<T>({
    queryKey: qk.dashboardSim(split),
    queryFn: () => api<T>("/dashboard/simulation", { query: { split } }),
    ...opts,
  });
}

// ---- Demo clock and reset -------------------------------------------------------------

export function useDemoClock(opts?: Opts<DemoClock>) {
  const { isSignedIn } = useAuth();
  return useQuery<DemoClock>({
    queryKey: qk.clock,
    queryFn: () => api<DemoClock>("/demo/clock"),
    enabled: isSignedIn,
    refetchInterval: 30_000,
    ...opts,
  });
}

/** The current demo time as a Date. Use this, not new Date(), when deciding overdue or due soon. */
export function useDemoNow(): Date {
  const { data } = useDemoClock();
  return data?.now ? new Date(data.now) : new Date();
}

/** Advance the demo clock. Refreshes everything because overdue flags change. */
export function useAdvanceClock() {
  const qc = useQueryClient();
  return useMutation<DemoClock, unknown, { hours: number }>({
    mutationFn: (body) => api<DemoClock>("/demo/clock/advance", { method: "POST", body }),
    onSuccess: (data) => {
      qc.setQueryData(qk.clock, data);
      void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "demo" });
    },
  });
}

export function useResetDemo() {
  const qc = useQueryClient();
  return useMutation<unknown, unknown, void>({
    mutationFn: () => api("/demo/reset", { method: "POST", anonymous: false }),
    onSuccess: () => void qc.invalidateQueries(),
  });
}
