import { createContext, useContext, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Badge, Card, DueChip, OwnerChip } from "@/components";
import { formatDate } from "@/lib/format";
import type { PatientCase } from "./api";

/** The signed-in patient's case, loaded once by the shell and shared by every screen. */
const CaseContext = createContext<PatientCase | null>(null);
export const CaseProvider = CaseContext.Provider;

export function useCurrentCase(): PatientCase {
  const c = useContext(CaseContext);
  if (!c) throw new Error("useCurrentCase must be used inside the patient shell");
  return c;
}

export function firstName(name: string | null | undefined): string {
  return (name ?? "").trim().split(/\s+/)[0] ?? "";
}

export function PageTitle({ children }: { children: ReactNode }) {
  return <h1 className="text-xl font-semibold">{children}</h1>;
}

export function Prose({ children }: { children: ReactNode }) {
  return <p className="text-base leading-relaxed">{children}</p>;
}

export function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="m-0 flex list-disc flex-col gap-1.5 ps-5">
      {items.map((x) => (
        <li key={x}>{x}</li>
      ))}
    </ul>
  );
}

/** A calm note. Amber means "worth your attention", never failure. */
export function Notice({ tone = "info", title, children }: { tone?: "info" | "due" | "accent"; title?: ReactNode; children: ReactNode }) {
  const cls = tone === "due" ? "bg-due-soft text-due-ink" : tone === "accent" ? "bg-accent-soft text-accent-ink" : "bg-info-soft text-info-ink";
  return (
    <div role={tone === "due" ? "alert" : "status"} className={`flex flex-col gap-1 rounded-card p-4 ${cls}`}>
      {title && <p className="font-semibold">{title}</p>}
      <div className="text-base leading-relaxed">{children}</div>
    </div>
  );
}

/** Maps the case state and next step to the screen where the patient acts on it. */
export function screenFor(labelKey: string | undefined): string | null {
  switch (labelKey) {
    case "patient_acknowledge":
      return "/patient/understand";
    case "choose_confirmation_method":
    case "complete_home_readings":
    case "attend_abpm":
      return "/patient/confirm";
    case "book_appointment":
      return "/patient/visit";
    case "four_week_review":
    case "consider_closure":
      return "/patient/weekly";
    default:
      return null;
  }
}

/** The one next step: what it is, who acts, who is accountable and by when, in plain words. */
export function NextStepCard({ compact = false }: { compact?: boolean }) {
  const { t, i18n } = useTranslation("patient");
  const c = useCurrentCase();
  const step = c.next_step;
  if (c.state === "CLOSED" || !step) return null;
  const known = t(`next.${step.label_key}.title`, { defaultValue: "" }) !== "";
  const key = known ? step.label_key : "default";
  const patientActs = step.acting_role === "patient";
  const target = screenFor(step.label_key);
  return (
    <Card as="section" title={t("next.title")}>
      <div className="flex flex-col gap-3">
        <div>
          <p className="text-lg font-semibold">{t(`next.${key}.title`)}</p>
          <p className="text-muted">{t(`next.${key}.text`)}</p>
        </div>
        <dl className="m-0 grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted">{t("next.doneBy")}</dt>
          <dd className="m-0 font-medium">{patientActs ? t("next.you") : t("next.careTeam")}</dd>
          <dt className="text-muted">{t("next.responsible")}</dt>
          <dd className="m-0">
            <OwnerChip name={step.owner_person?.name} role={step.owner_role} />
          </dd>
          <dt className="text-muted">{t("next.by")}</dt>
          <dd className="m-0 flex flex-wrap items-center gap-2">
            <span className="font-medium">
              <bdi>{formatDate(step.due_at, i18n.language)}</bdi>
            </span>
            <DueChip dueAt={step.due_at} overdue={step.overdue} audience="patient" />
          </dd>
        </dl>
        {!compact && target && patientActs && (
          <Link
            to={target}
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-accent px-4 py-2 font-semibold text-white hover:bg-accent-strong"
          >
            {t(`next.${key}.title`)}
          </Link>
        )}
      </div>
    </Card>
  );
}

export function StatusBadge() {
  const { t } = useTranslation("patient");
  const c = useCurrentCase();
  return <Badge tone="accent">{t(`status.${c.state}`)}</Badge>;
}
