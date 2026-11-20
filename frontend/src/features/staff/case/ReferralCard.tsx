import { useTranslation } from "react-i18next";
import { Badge, Card } from "@/components";
import { useAuth } from "@/api/auth";
import { formatDateTime } from "@/lib/format";
import { pickText } from "@/lib/i18nField";
import { usePersonText } from "../PersonLabel";
import type { CaseDetail } from "../types";

const TONE = { PENDING: "info", ACCEPTED: "accent", REJECTED: "urgent" } as const;

export function ReferralCard({ detail }: { detail: CaseDetail }) {
  const { t, i18n } = useTranslation("staff");
  const { user } = useAuth();
  const person = usePersonText();
  const r = detail.referral;
  const a = detail.appointment;
  const history = detail.referrals_history.filter((h) => !r || h.id !== r.id);

  return (
    <Card title={t("referral.title")}>
      {!r && !a && <p className="text-sm text-muted">{t("referral.none")}</p>}
      {r && (
        <div className="flex flex-col gap-1 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={TONE[r.status]}>{t(`referral.status.${r.status}`)}</Badge>
            <span className="text-muted">{formatDateTime(r.created_at, i18n.language)}</span>
          </div>
          <p>{t("referral.route", { from: r.from_person ? person(r.from_person) : t("referral.unknown"), to: r.to_person ? person(r.to_person) : pickText(r.to_service_i18n, r.to_service ?? t("referral.unknown")) })}</p>
          <p>
            <span className="font-medium">{t("referral.reason")}</span>{" "}
            {r.reason || (user?.role === "coordinator" ? t("clinicianOnly") : "")}
          </p>
          {r.rejection_reason && (
            <p className="rounded-lg bg-urgent-soft px-3 py-2 text-urgent-ink">
              <span className="font-medium">{t("referral.rejectionReason")}</span> {r.rejection_reason}
            </p>
          )}
        </div>
      )}
      {history.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-medium text-accent-ink">{t("referral.history", { count: history.length })}</summary>
          <ul className="mt-2 flex flex-col gap-2">
            {history.map((h) => (
              <li key={h.id} className="rounded-lg bg-surface-2 p-2">
                <Badge tone={TONE[h.status]}>{t(`referral.status.${h.status}`)}</Badge>{" "}
                {t("referral.route", { from: h.from_person ? person(h.from_person) : t("referral.unknown"), to: h.to_person ? person(h.to_person) : pickText(h.to_service_i18n, h.to_service ?? t("referral.unknown")) })}
                {h.rejection_reason && <p className="text-muted">{h.rejection_reason}</p>}
              </li>
            ))}
          </ul>
        </details>
      )}
      {a && (
        <div className="mt-3 border-t border-line pt-3 text-sm">
          <h3 className="font-semibold">{t("appointment.title")}</h3>
          <p>
            {formatDateTime(a.starts_at, i18n.language)}, {person(a.provider_person)}
          </p>
          <p className="text-muted">
            {pickText(a.location_i18n, a.location)}. {t(`appointment.status.${a.status}`, { defaultValue: a.status })}
          </p>
        </div>
      )}
    </Card>
  );
}
