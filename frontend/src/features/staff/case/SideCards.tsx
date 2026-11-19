import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { Badge, Card, DueChip, EmptyState, JourneySteps, Timeline } from "@/components";
import type { JourneyStepData, TimelineEvent } from "@/api/types";
import { formatDateTime } from "@/lib/format";
import { useLabels } from "../labels";
import { usePersonText } from "../PersonLabel";
import type { CaseDetail } from "../types";

const CLINICAL_TEXT_EVENTS = new Set([
  "CASE_CLOSED",
  "VISIT_RECORDED",
  "URGENT_REVIEW_COMPLETED",
  "CONFIRMATION_REVIEWED",
  "REFERRAL_SENT",
  "ECONSULT_ASKED",
  "ECONSULT_ANSWERED",
]);

export function ProgressCard({ detail }: { detail: CaseDetail }) {
  const { t } = useTranslation("staff");
  const steps: JourneyStepData[] = detail.progress.map((p) => ({ state: p.state, done_at: p.reached_at, current: p.current }));
  return (
    <Card title={t("progress.title")}>
      <JourneySteps currentState={detail.state} steps={steps} />
    </Card>
  );
}

export function ConsentCard({ detail }: { detail: CaseDetail }) {
  const { t, i18n } = useTranslation("staff");
  const labels = useLabels();
  return (
    <Card title={t("consent.title")}>
      <p className="mb-2 text-sm text-muted">{t("consent.intro")}</p>
      <ul className="flex flex-col gap-2 text-sm">
        {detail.consents.map((c) => (
          <li key={`${c.purpose}-${c.channel ?? ""}`} className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {labels.consent(c.purpose)}
              {c.channel ? ` (${t(`channel.${c.channel}`)})` : ""}
            </span>
            <span className="flex items-center gap-2">
              <Badge tone={c.granted ? "accent" : "due"}>{c.granted ? t("consent.granted") : t("consent.withdrawn")}</Badge>
              <span className="text-xs text-muted">
                {formatDateTime(c.granted ? c.granted_at : c.withdrawn_at, i18n.language)}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function PlanCard({ detail }: { detail: CaseDetail }) {
  const { t, i18n } = useTranslation("staff");
  const labels = useLabels();
  return (
    <Card title={t("plan.title")}>
      {detail.plan.length === 0 ? (
        <EmptyState description={t("plan.empty")} />
      ) : (
        <>
          {!detail.plan_active && <p className="mb-2 rounded-lg bg-due-soft px-3 py-2 text-sm text-due-ink">{t("plan.stopped")}</p>}
          <p className="mb-2 text-sm text-muted">{t("plan.intro")}</p>
          <ul className="flex flex-col gap-2 text-sm">
            {detail.plan.map((w) => (
              <li key={w.week_index} className="rounded-lg border border-line p-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">
                    {t("plan.week", { n: w.week_index + 1 })}: {labels.planAction(w.action_key)}
                  </span>
                  <span className="flex items-center gap-2">
                    <Badge>{t(`plan.size.${w.size}`)}</Badge>
                    <Badge tone={w.status === "done" ? "accent" : w.status ? "info" : "neutral"}>
                      {w.status ? t(`plan.status.${w.status}`) : t("plan.status.open")}
                    </Badge>
                  </span>
                </div>
                <p className="text-xs text-muted">
                  {formatDateTime(w.starts_at, i18n.language)}
                  {w.barrier ? `. ${t("plan.barrier", { barrier: t(`plan.barriers.${w.barrier}`) })}` : ""}
                </p>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

export function TasksCard({ detail }: { detail: CaseDetail }) {
  const { t } = useTranslation("staff");
  const labels = useLabels();
  const open = detail.tasks.filter((x) => x.status === "OPEN");
  if (open.length === 0) return null;
  return (
    <Card title={t("tasks.title")}>
      <ul className="flex flex-col gap-2 text-sm">
        {open.map((task) => (
          <li key={task.id} className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {labels.task(task.title_key)} <span className="text-muted">({t(`roleShort.${task.owner_role}`)})</span>
            </span>
            <DueChip dueAt={task.due_at} overdue={task.overdue} />
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function AuditCard({ detail }: { detail: CaseDetail }) {
  const { t } = useTranslation("staff");
  const labels = useLabels();
  const [showViews, setShowViews] = useState(false);
  const { user } = useAuth();
  const person = usePersonText();
  const coordinator = user?.role === "coordinator";
  // A coordinator never receives the clinical free text of these events. Say so instead of leaving a gap.
  const events: TimelineEvent[] = detail.timeline
    .filter((e) => showViews || e.type !== "CASE_VIEWED")
    .map((e) => ({
      ...e,
      actor_name: e.actor_person ? person(e.actor_person) : e.actor_name,
      reason: e.reason ?? (coordinator && CLINICAL_TEXT_EVENTS.has(e.type) ? t("clinicianOnly") : null),
    }));
  return (
    <Card title={t("audit.title")}>
      <p className="mb-2 text-sm text-muted">{t("audit.intro")}</p>
      <label className="mb-3 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={showViews} onChange={(e) => setShowViews(e.target.checked)} className="size-4 accent-[var(--color-accent)]" />
        {t("audit.showViews")}
      </label>
      <div className="max-h-[32rem] overflow-y-auto pe-1">
        <Timeline events={events} eventLabel={(ev) => labels.event(ev.type)} />
      </div>
    </Card>
  );
}

export function ClosureSummary({ detail }: { detail: CaseDetail }) {
  const { t, i18n } = useTranslation("staff");
  const labels = useLabels();
  const person = usePersonText();
  const c = detail.closure;
  if (!c) return null;
  return (
    <Card title={t("closure.recorded")}>
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted">{t("closure.evidenceType")}</dt>
          <dd className="font-medium">{labels.evidence(c.evidence_type)}</dd>
        </div>
        <div>
          <dt className="text-muted">{t("closure.closedBy")}</dt>
          <dd className="font-medium">
            {person(c.closed_by_person)}, {formatDateTime(c.closed_at, i18n.language)}
          </dd>
        </div>
        {c.evidence_ref && (
          <div>
            <dt className="text-muted">{t("closure.refLegend")}</dt>
            <dd className="font-medium">{c.evidence_ref}</dd>
          </div>
        )}
        <div className="sm:col-span-2">
          <dt className="text-muted">{t("closure.note")}</dt>
          <dd className={c.decision_note ? "font-medium" : "text-muted"}>{c.decision_note ?? t("clinicianOnly")}</dd>
        </div>
      </dl>
    </Card>
  );
}
