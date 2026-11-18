import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, DueChip, EmptyState, JourneySteps, Timeline } from "@/components";
import type { JourneyStepData, TimelineEvent } from "@/api/types";
import { formatDateTime } from "@/lib/format";
import { useLabels } from "../labels";
import type { CaseDetail } from "../types";

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
  const events: TimelineEvent[] = detail.timeline.filter((e) => showViews || e.type !== "CASE_VIEWED");
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
            {c.closed_by_name ?? ""}, {formatDateTime(c.closed_at, i18n.language)}
          </dd>
        </div>
        {c.evidence_ref && (
          <div>
            <dt className="text-muted">{t("closure.refLegend")}</dt>
            <dd className="font-medium">{c.evidence_ref}</dd>
          </div>
        )}
        {c.decision_note && (
          <div className="sm:col-span-2">
            <dt className="text-muted">{t("closure.note")}</dt>
            <dd className="font-medium">{c.decision_note}</dd>
          </div>
        )}
      </dl>
    </Card>
  );
}
