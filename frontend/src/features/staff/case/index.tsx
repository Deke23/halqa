import { useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { Badge, ErrorState, Loading } from "@/components";
import { useStaffCase } from "../api";
import { ActionsPanel } from "./ActionsPanel";
import { EconsultCard } from "./EconsultCard";
import { FhirDrawer } from "./FhirDrawer";
import { CaseHeader } from "./Header";
import { MessagesCard } from "./MessagesCard";
import { ReadingsCard } from "./ReadingsCard";
import { ReferralCard } from "./ReferralCard";
import { AuditCard, ClosureSummary, ConsentCard, PlanCard, ProgressCard, TasksCard } from "./SideCards";

/** Route /staff/cases/:id. Actions come only from the server's allowed_actions. */
export default function StaffCase() {
  const { t } = useTranslation("staff");
  const { id } = useParams();
  const q = useStaffCase(id);
  const { user } = useAuth();
  const [fhirOpen, setFhirOpen] = useState(false);

  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorState error={q.error} title={t("case.loadError")} onRetry={() => void q.refetch()} />;
  const detail = q.data;

  return (
    <div className="flex flex-col gap-5">
      <CaseHeader detail={detail} onOpenFhir={() => setFhirOpen(true)} />
      {detail.emergency_advice && detail.urgent && (
        <p role="note" className="rounded-lg bg-urgent-soft px-3 py-2 text-sm text-urgent-ink">
          <Badge tone="urgent">{t("header.emergencyAdvice")}</Badge>{" "}
          <span lang={detail.patient.language} dir={detail.patient.language === "ar" ? "rtl" : "ltr"}>{detail.emergency_advice.text}</span>
        </p>
      )}
      {detail.flags.care_coordination_withdrawn && detail.state !== "CLOSED" && (
        <div role="alert" className="rounded-lg border border-due bg-due-soft px-4 py-3 text-due-ink">
          <p className="font-semibold">{t("banner.coordinationTitle")}</p>
          <p className="text-sm">{t("banner.coordinationBody")}</p>
        </div>
      )}
      <ActionsPanel detail={detail} />
      <div className="grid gap-5 xl:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-5 xl:col-span-2">
          <ClosureSummary detail={detail} />
          <ReadingsCard detail={detail} />
          <ReferralCard detail={detail} />
          <MessagesCard detail={detail} />
          <EconsultCard detail={detail} />
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          <ProgressCard detail={detail} />
          <TasksCard detail={detail} />
          <ConsentCard detail={detail} />
          <PlanCard detail={detail} />
          <AuditCard detail={detail} />
        </div>
      </div>
      {user?.role === "clinician" && <FhirDrawer caseId={String(detail.id)} open={fhirOpen} onClose={() => setFhirOpen(false)} />}
    </div>
  );
}
