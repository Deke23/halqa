import { createContext, useContext, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Badge, DueChip, OwnerChip } from "@/components";
import { personName, pickText } from "@/lib/i18nField";
import { cx } from "@/lib/cx";
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
  return <h1 className="m-0 text-2xl font-semibold leading-tight">{children}</h1>;
}

/** Flat hair-border block. One level only: no panel inside a panel. */
export function Panel({ title, action, children, className, id }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cx("rise-in rounded-card border border-line bg-surface p-5", className)}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {title && <h2 className="m-0 text-lg font-semibold">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** A clinical value, time or count: mono, left to right, Latin digits. */
export function Readout({ children, className }: { children: ReactNode; className?: string }) {
  return <bdi className={cx("readout", className)}>{children}</bdi>;
}

export const primaryLink =
  "inline-flex min-h-12 w-full items-center justify-center rounded-control bg-accent px-5 py-2 text-center text-base font-semibold text-white hover:bg-accent-strong";

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
    <Panel title={t("next.title")}>
      <div className="flex flex-col gap-4">
        <div>
          <p className="m-0 text-lg font-semibold">{t(`next.${key}.title`)}</p>
          <p className="m-0 mt-1 text-muted">{t(`next.${key}.text`)}</p>
        </div>
        <dl className="m-0 grid grid-cols-[auto_1fr] items-center gap-x-5 gap-y-2.5 text-sm">
          <dt className="text-muted">{t("next.doneBy")}</dt>
          <dd className="m-0 font-medium">{patientActs ? t("next.you") : t("next.careTeam")}</dd>
          <dt className="text-muted">{t("next.responsible")}</dt>
          <dd className="m-0">
            <OwnerChip name={personName(step.owner_person)} role={pickText(step.owner_person?.roles, "") || step.owner_role} />
          </dd>
          <dt className="text-muted">{t("next.by")}</dt>
          <dd className="m-0 flex flex-wrap items-center gap-2">
            <bdi className="font-medium">{formatDate(step.due_at, i18n.language)}</bdi>
            <DueChip dueAt={step.due_at} overdue={step.overdue} audience="patient" />
          </dd>
        </dl>
        {!compact && target && patientActs && (
          <Link to={target} className={primaryLink}>
            {t(`next.${key}.title`)}
          </Link>
        )}
      </div>
    </Panel>
  );
}

export function StatusBadge() {
  const { t } = useTranslation("patient");
  const c = useCurrentCase();
  return <Badge tone="accent">{t(`status.${c.state}`)}</Badge>;
}

/** Server text with a per-language map next to it (`<field>_i18n`). Falls back to the plain string. */
export function i18nOf(obj: unknown, field: string): string {
  const o = (obj ?? {}) as Record<string, unknown>;
  return pickText(o[`${field}_i18n`] as Record<string, string> | undefined, (o[field] as string | undefined) ?? "");
}

/** Radio group whose inputs carry their own accessible name (the answer text), with the legend as the group name. */
export function ChoiceGroup({
  name, legend, options, value, onChange, inline,
}: {
  name: string;
  legend: ReactNode;
  options: { value: string; label: ReactNode; text: string }[];
  value: string;
  onChange: (v: string) => void;
  inline?: boolean;
}) {
  return (
    <fieldset className="m-0 min-w-0 border-0 p-0">
      <legend className="mb-3 p-0 text-sm font-medium">{legend}</legend>
      <div className={cx("flex gap-2", inline ? "flex-row flex-wrap" : "flex-col")}>
        {options.map((o) => {
          const checked = o.value === value;
          return (
            <label
              key={o.value}
              className={cx(
                "flex min-h-11 cursor-pointer items-start gap-3 rounded-control border px-3 py-2.5",
                checked ? "border-accent bg-accent-soft" : "border-line-strong bg-surface hover:bg-surface-2",
              )}
            >
              <input
                type="radio"
                name={name}
                value={o.value}
                checked={checked}
                aria-label={o.text}
                onChange={() => onChange(o.value)}
                className="mt-1 size-4 accent-[var(--color-accent)]"
              />
              <span className="font-medium">{o.label}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
