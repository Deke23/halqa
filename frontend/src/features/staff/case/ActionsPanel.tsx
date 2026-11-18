import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { Button, Card } from "@/components";
import type { Action, CaseDetail } from "../types";
import { ActionDialog, FORM_ACTIONS } from "./ActionDialog";
import { ClosureDialog } from "./ClosureDialog";

/** Order in which buttons appear. Only actions the server lists in allowed_actions are shown. */
const ORDER: Action[] = [
  "complete_urgent_review",
  "notify",
  "choose_confirmation",
  "review_confirmation",
  "refer",
  "accept_referral",
  "reject_referral",
  "book_appointment",
  "record_visit",
  "assign_owner",
  "add_reading",
  "escalate",
  "close",
  "reopen",
];

export function ActionsPanel({ detail }: { detail: CaseDetail }) {
  const { t } = useTranslation("staff");
  const { user } = useAuth();
  const [active, setActive] = useState<Action | null>(null);

  const allowed = new Set(detail.allowed_actions);
  const shown = ORDER.filter((a) => allowed.has(a) && (FORM_ACTIONS.includes(a) || a === "close"));
  const isClinician = user?.role === "clinician";
  const isCoordinator = user?.role === "coordinator";
  const shareWithdrawn = detail.consents.some((c) => c.purpose === "share_with_receiving_provider" && !c.granted);
  const referBlocked = isClinician && detail.state === "CONFIRMED" && !allowed.has("refer") && shareWithdrawn;

  return (
    <Card title={t("actions.title")}>
      <p className="mb-3 text-sm text-muted">{t("actions.intro")}</p>
      {shown.length === 0 && <p className="text-sm text-muted">{t("actions.none")}</p>}
      <div className="flex flex-wrap gap-2">
        {shown.map((a, i) => (
          <Button key={a} variant={i === 0 ? "primary" : "secondary"} onClick={() => setActive(a)}>
            {t(`action.${a}.title`)}
          </Button>
        ))}
      </div>
      {referBlocked && (
        <p role="note" className="mt-3 rounded-lg bg-due-soft px-3 py-2 text-sm text-due-ink">
          {t("actions.referBlocked")}
        </p>
      )}
      {isCoordinator && detail.state !== "CLOSED" && (
        <p className="mt-3 rounded-lg bg-surface-2 px-3 py-2 text-sm text-muted">{t("actions.coordinatorCannotClose")}</p>
      )}
      {active && active !== "close" && <ActionDialog action={active} detail={detail} onClose={() => setActive(null)} />}
      {active === "close" && <ClosureDialog detail={detail} onClose={() => setActive(null)} />}
    </Card>
  );
}
