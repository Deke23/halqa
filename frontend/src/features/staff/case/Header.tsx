import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { Badge, BPReading, useDurationText, Button, DueChip, SimulatedTag, StateBadge } from "@/components";
import { formatDateTime } from "@/lib/format";
import { personName } from "@/lib/i18nField";
import { CaseRing } from "../CaseRing";
import { useLabels } from "../labels";
import { OwnerCell } from "../PersonLabel";
import type { CaseDetail } from "../types";

export function CaseHeader({ detail, onOpenFhir }: { detail: CaseDetail; onOpenFhir: () => void }) {
  const { t, i18n } = useTranslation("staff");
  const labels = useLabels();
  const duration = useDurationText();
  const { user } = useAuth();
  const p = detail.patient;
  const step = detail.next_step;
  const closed = detail.state === "CLOSED";
  const flags = detail.flags;
  const urgent = detail.urgent && !closed;
  const reviewTask = detail.tasks.find((x) => x.type === "URGENT_REVIEW" && x.status === "OPEN");
  const dueAt = (detail as { urgent_review_due_at?: string | null }).urgent_review_due_at ?? reviewTask?.due_at ?? null;
  const urgentTask = flags.urgent_review_pending && dueAt ? { due_at: dueAt, overdue: reviewTask?.overdue ?? false } : null;

  return (
    <header className="rise-in flex flex-col gap-4 rounded-card border border-line bg-surface p-5">
      <Link
        to={user?.role === "clinician" ? "/staff/worklist" : "/staff/queue"}
        className="w-fit text-sm text-accent-ink underline-offset-2 hover:underline"
      >
        {user?.role === "clinician" ? t("header.backWorklist") : t("header.backQueue")}
      </Link>

      <div className="flex flex-wrap items-start gap-5">
        <CaseRing state={detail.state} urgent={urgent} size={72} readout />
        <div className="min-w-0 flex-1">
          <h1 className="flex flex-wrap items-center gap-x-3 gap-y-1 text-2xl font-semibold">
            <bdi>{personName(p)}</bdi>
            <BPReading systolic={detail.index_systolic} diastolic={detail.index_diastolic} size="md" />
          </h1>
          <p className="mt-1 text-sm text-muted">
            <bdi dir="ltr" className="readout">{p.ref}</bdi>
            {" · "}
            {t("header.patientLine", { age: p.age, sex: t(`sex.${p.sex}`, { defaultValue: p.sex }), language: t(`language.${p.language}`) })}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <StateBadge state={detail.state} />
            {detail.severity === "SEVERE" && <Badge tone="urgent">{t("header.severe")}</Badge>}
            {urgent && <Badge tone="urgent">{t("common:urgent")}</Badge>}
            {flags.urgent_review_pending && <Badge tone="urgent">{t("header.urgentReviewPending")}</Badge>}
            {flags.rejected && <Badge tone="urgent">{t("header.rejected")}</Badge>}
            {flags.escalated && !closed && <Badge tone="urgent">{t("header.escalated", { level: step?.escalation_level ?? 2 })}</Badge>}
            {flags.needs_clinician_decision && <Badge tone="due">{t("header.needsDecision")}</Badge>}
            {flags.care_coordination_withdrawn && <Badge tone="due">{t("header.coordinationWithdrawn")}</Badge>}
            {flags.closure_ready && <Badge tone="accent">{t("header.closureReady")}</Badge>}
            <span className="text-xs text-muted">
              {t("header.source", { source: t(`sourceSystem.${detail.source_system}`, { defaultValue: detail.source_system }) })} <SimulatedTag />
            </span>
          </div>
          {urgent && detail.urgent_reason && (
            <p className="mt-2 text-sm text-urgent-ink">
              {t("header.urgentReason", { reason: t(`header.urgentReasons.${detail.urgent_reason}`, { defaultValue: detail.urgent_reason }) })}
            </p>
          )}
        </div>
        {user?.role === "clinician" && (
          <Button variant="secondary" onClick={onOpenFhir}>
            {t("fhir.open")}
          </Button>
        )}
      </div>

      {urgentTask && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-urgent bg-urgent-soft px-4 py-3 text-urgent-ink">
          <Badge tone="urgent">{t("header.urgentReviewDue")}</Badge>
          <DueChip dueAt={urgentTask.due_at} overdue={urgentTask.overdue} />
          <span className="text-sm">{formatDateTime(urgentTask.due_at, i18n.language)}</span>
          <span className="text-sm">{t("header.urgentReviewHint")}</span>
        </div>
      )}
      <dl className="grid gap-4 border-t border-line pt-4 sm:grid-cols-3">
        <div>
          <dt className="text-xs font-medium text-muted">{urgentTask ? t("header.routineNextStep") : t("header.nextStep")}</dt>
          <dd className="mt-1 font-semibold">{closed ? t("header.closedNoStep") : labels.nextStep(step?.label_key)}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-muted">{t("header.owner")}</dt>
          <dd className="mt-1">
            {closed ? <span className="text-muted">{t("header.closedNoOwner")}</span> : <OwnerCell person={step?.owner_person ?? detail.owner_person} role={detail.owner_role} />}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-muted">{t("header.due")}</dt>
          <dd className="mt-1 flex flex-wrap items-center gap-2">
            {closed || !step ? (
              <span className="text-muted">{t("header.noDue")}</span>
            ) : (
              <>
                <DueChip dueAt={step.due_at} overdue={step.overdue} />
                <span className="text-xs text-muted">{formatDateTime(step.due_at, i18n.language)}</span>
                <span className="text-xs text-muted">{t("header.serviceLevel", { hours: duration(step.service_level_h) })}</span>
              </>
            )}
          </dd>
        </div>
      </dl>
    </header>
  );
}
