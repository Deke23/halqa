/**
 * Typed query and mutation hooks for the patient app and the phone thread.
 * Types come from the generated schema. The shell hooks are reused where they fit.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ApiError } from "@/api/client";
import { qk, useCaseAction, useConfig, useMyCase } from "@/api/hooks";
import type { components } from "@/api/schema";

type S = components["schemas"];
export type PatientCase = S["CaseDetail"];
export type MessageOut = S["MessageOut"];
export type SlotOut = S["SlotOut"];
export type DiaryOut = S["DiaryOut"];
export type PlanWeekOut = S["PlanWeekOut"];
export type ConsentOut = S["ConsentOut"];
export type ReadingOut = S["ReadingOut"];
export type ConfigOut = S["ConfigOut"];
export type Feedback = S["Feedback"];
export type Language = S["Language"];
export type Action = S["Action"];

export function usePatientCase() {
  return useMyCase<PatientCase>();
}

/** Posts an action as the signed-in patient. The result carries `feedback` when the backend has a message. */
export function usePatientAction(caseId: number | undefined) {
  return useCaseAction<PatientCase>(caseId === undefined ? undefined : String(caseId));
}

/** Outgoing template messages are re-rendered by the backend in the language asked for. */
export function useThread(language: string, poll = false) {
  return useQuery<MessageOut[]>({
    queryKey: [...qk.myMessages, language],
    queryFn: () => api<MessageOut[]>("/my/messages", { query: { language } }),
    refetchInterval: poll ? 4000 : false,
  });
}

export function useDiary() {
  return useQuery<DiaryOut>({ queryKey: ["my", "diary"], queryFn: () => api<DiaryOut>("/my/diary"), staleTime: 60_000 });
}

export function usePatientSlots(caseId: number | undefined, enabled: boolean) {
  return useQuery<SlotOut[]>({
    queryKey: qk.slots(String(caseId ?? "")),
    queryFn: () => api<SlotOut[]>(`/cases/${caseId}/slots`),
    enabled: enabled && caseId !== undefined,
  });
}

export function useRegionConfig(region: string | undefined) {
  const q = useConfig<ConfigOut>();
  return { ...q, region: q.data?.regions.find((r) => r.region === region) };
}

/** Sends a keyword or reading reply on the phone thread. Returns the whole thread. */
export function useSendReply() {
  const qc = useQueryClient();
  return useMutation<MessageOut[], ApiError, { text: string }>({
    mutationFn: (body) => api<MessageOut[]>("/my/messages/reply", { method: "POST", body }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.myMessages });
      void qc.invalidateQueries({ queryKey: qk.cases });
    },
  });
}

// ---------------------------------------------------------------------------------------------
// Helpers shared by several screens

/** Teach-back options are the numbers in the question text. The backend text is used as written. */
export function parseTeachBack(text: string): { question: string; options: { id: string; label: string }[] } {
  const lines = text.split("\n");
  const options: { id: string; label: string }[] = [];
  const stem: string[] = [];
  for (const line of lines) {
    const m = /^\s*(\d)\.\s+(.*)$/.exec(line);
    if (m) options.push({ id: m[1]!, label: m[2]!.trim() });
    else stem.push(line);
  }
  return { question: stem.join(" ").trim(), options };
}

export function latestMessage(messages: MessageOut[] | undefined, templateId: string): MessageOut | undefined {
  return [...(messages ?? [])].reverse().find((m) => m.template_id === templateId);
}

/** The open plan week is the newest one without a check-in. */
export function currentWeek(plan: PlanWeekOut[]): PlanWeekOut | undefined {
  return [...plan].sort((a, b) => b.week_index - a.week_index).find((w) => w.status === null);
}

export function pastWeeks(plan: PlanWeekOut[]): PlanWeekOut[] {
  return plan.filter((w) => w.status !== null).sort((a, b) => b.week_index - a.week_index);
}

/** Distinct UTC days that have a home reading. */
export function homeReadingDays(readings: ReadingOut[]): number {
  return new Set(readings.filter((r) => r.source === "HOME_CUFF" || r.source === "ABPM").map((r) => r.taken_at.slice(0, 10))).size;
}

// ---------------------------------------------------------------------------------------------
// Demo shortcuts: act as another persona in the background.

const tokenCache = new Map<string, { token: string; name: string }>();

function toApiError(status: number, payload: unknown): ApiError {
  let code = `http_${status}`;
  let message = "Request failed";
  if (payload && typeof payload === "object") {
    const p = payload as Record<string, unknown>;
    const d = (p.detail ?? p) as unknown;
    if (typeof d === "string") message = d;
    else if (d && typeof d === "object" && !Array.isArray(d)) {
      const o = d as Record<string, unknown>;
      if (typeof o.code === "string") code = o.code;
      if (typeof o.message === "string") message = o.message;
    } else if (Array.isArray(d)) message = d.map((x) => (x as { msg?: string }).msg ?? "").join("; ");
  }
  return { status, code, message };
}

async function rawFetch<T>(path: string, token: string | null, method: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw { status: 0, code: "network_error", message: "backend_unreachable" } satisfies ApiError;
  }
  const text = await res.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }
  if (!res.ok) throw toApiError(res.status, payload);
  return payload as T;
}

async function tokenFor(persona: string, fresh = false): Promise<{ token: string; name: string }> {
  const cached = tokenCache.get(persona);
  if (cached && !fresh) return cached;
  const res = await rawFetch<S["AuthResponse"]>("/auth/guest", null, "POST", { persona });
  const entry = { token: res.token, name: res.user.name };
  tokenCache.set(persona, entry);
  return entry;
}

export interface ActedAs {
  who: string;
  detail: PatientCase;
}

/**
 * Calls the real action endpoint as another persona. The server checks the role and writes the audit
 * event, so the transition is genuine. The patient's own session token is never touched.
 */
export async function actAs(persona: string, caseId: number, action: Action, payload: Record<string, unknown> = {}): Promise<ActedAs> {
  const run = async (fresh: boolean) => {
    const { token, name } = await tokenFor(persona, fresh);
    const detail = await rawFetch<PatientCase>(`/cases/${caseId}/actions`, token, "POST", { action, payload });
    return { who: name, detail };
  };
  try {
    return await run(false);
  } catch (e) {
    if ((e as ApiError).status === 401) return run(true);
    throw e;
  }
}

export async function slotsAs(persona: string, caseId: number): Promise<SlotOut[]> {
  const { token } = await tokenFor(persona);
  return rawFetch<SlotOut[]>(`/cases/${caseId}/slots`, token, "GET");
}

export async function advanceClockAs(persona: string, hours: number): Promise<void> {
  const { token } = await tokenFor(persona);
  await rawFetch("/demo/clock/advance", token, "POST", { hours });
}

export async function replyAs(text: string): Promise<void> {
  await rawFetch("/my/messages/reply", (await currentToken()) ?? null, "POST", { text });
}

async function currentToken(): Promise<string | null> {
  try {
    return sessionStorage.getItem("halqa.token");
  } catch {
    return null;
  }
}

/** Refresh every query that depends on case state after a shortcut. */
export function useRefreshAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries();
}
