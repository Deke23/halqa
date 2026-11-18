import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { Badge, BPReading, Button, DueChip, SimulatedTag, StateBadge } from "@/components";
import { formatDateTime } from "@/lib/format";
import { OwnerCell } from "../OwnerCell";
import { useLabels } from "../labels";
import type { CaseDetail } from "../types";

export function CaseHeader({ detail, onOpenFhir }: { detail: CaseDetail; onOpenFhir: () => void }) {
  const { t, i18n } = useTranslation("staff");
  const { t: tc } = useTranslation();
  const labels = useLabels();
  const { user } = useAuth();
  const p = detail.patient;
  const step = detail.next_step;
  const closed = detail.state === "CLOSED";
  const flags = detail.flags;

  return (
    <header className="flex flex-col gap-4 rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to={user?.role === "clinician" ? "/staff/worklist" : "/staff/queue"} className="text-sm text-accent-ink underline-offset-2 hover:underline">
            {user?.role === "clinician" ? t("header.backWorklist") : t("header.backQueue")}
          </Link>
          <h1 className="mt-1 flex flex-wrap items-center gap-3 text-2xl font-semibold">
            <span>{p.display_name}</span>
            <BPReading systolic={detail.index_systolic} diastolic={detail.index_diastolic} size="md" />
          </h1>
          <p className="text-sm text-muted">
            <bdi dir="ltr" className="clinical">{p.ref}</bdi>
            {", "}
            {t("header.patientLine", { age: p.age, sex: t(`sex.${p.sex}`, { defaultValue: p.sex }), language: t(`language.${p.language}`) })}
            {". "}
            {p.organisation}
          </p>
          <p className="text-xs text-muted">
            {t("header.source", { source: t(`sourceSystem.${detail.source_system}`, { defaultValue: detail.source_system }) })}{" "}
            <SimulatedTag />
          </p>
        </div>
        <Button variant="secondary" onClick={onOpenFhir}>
          {t("fhir.open")}
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <StateBadge state={detail.state} />
        {detail.severity === "SEVERE" && <Badge tone="urgent">{t("header.severe")}</Badge>}
        {detail.urgent && !closed && <Badge tone="urgent">{tc("urgent")}</Badge>}
        {flags.urgent_review_pending && <Badge tone="urgent">{t("header.urgentReviewPending")}</Badge>}
        {flags.rejected && <Badge tone="urgent">{t("header.rejected")}</Badge>}
        {flags.escalated && !closed && <Badge tone="urgent">{t("header.escalated", { level: step?.escalation_level ?? 2 })}</Badge>}
        {flags.needs_clinician_decision && <Badge tone="due">{t("header.needsDecision")}</Badge>}
        {flags.closure_ready && <Badge tone="accent">{t("header.closureReady")}</Badge>}
      </div>
      {detail.urgent && detail.urgent_reason && !closed && (
        <p className="text-sm text-urgent-ink">{t("header.urgentReason", { reason: t(`header.urgentReasons.${detail.urgent_reason}`, { defaultValue: detail.urgent_reason }) })}</p>
      )}

      <dl className="grid gap-4 sm:grid-cols-3">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{t("header.nextStep")}</dt>
          <dd className="mt-1 font-medium">{closed ? t("header.closedNoStep") : labels.nextStep(step?.label_key)}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{t("header.owner")}</dt>
          <dd className="mt-1">
            <OwnerCell name={detail.owner_name} role={detail.owner_role} />
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{t("header.due")}</dt>
          <dd className="mt-1 flex flex-col items-start gap-1">
            {closed || !step ? (
              <span className="text-muted">{t("header.noDue")}</span>
            ) : (
              <>
                <DueChip dueAt={step.due_at} overdue={step.overdue} />
                <span className="text-xs text-muted">{formatDateTime(step.due_at, i18n.language)}</span>
                <span className="text-xs text-muted">{t("header.serviceLevel", { hours: step.service_level_h })}</span>
              </>
            )}
          </dd>
        </div>
      </dl>
    </header>
  );
}
