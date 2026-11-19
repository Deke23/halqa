import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BPReading, Card } from "@/components";
import { formatDate } from "@/lib/format";
import { latestMessage, useThread } from "./api";
import { NextStepCard, Notice, PageTitle, StatusBadge, firstName, useCurrentCase } from "./ui";

const rowLink =
  "flex min-h-11 flex-col gap-0.5 rounded-lg border border-line bg-surface px-4 py-3 hover:bg-surface-2";

export default function Home() {
  const { t } = useTranslation("patient");
  const c = useCurrentCase();
  const state = c.state;
  const afterAck = state !== "RESULT_ISSUED" && state !== "NOTIFIED";
  const afterConfirm = ["CONFIRMED", "REFERRED", "APPOINTMENT_BOOKED", "IN_CARE", "CLOSED"].includes(state);

  if (state === "CLOSED") return <ClosedSummary />;

  const links: { to: string; key: string }[] = [];
  if (state === "NOTIFIED") links.push({ to: "/patient/understand", key: "understand" });
  if (afterAck) links.push({ to: "/patient/confirm", key: "confirm" });
  if (afterConfirm) links.push({ to: "/patient/visit", key: "visit" });
  if (state === "IN_CARE") {
    links.push({ to: "/patient/weekly", key: "weekly" });
    links.push({ to: "/patient/weekly#diary", key: "diary" });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <PageTitle>{t("home.hello", { name: firstName(c.patient.display_name) })}</PageTitle>
        <p className="text-muted">{t("home.intro")}</p>
        <div>
          <StatusBadge />
        </div>
      </div>

      <Card title={t("home.yourReading")} action={<Link to="/patient/result" className="text-sm font-medium text-accent-ink underline">{t("home.seeResult")}</Link>}>
        <div className="flex flex-col gap-1">
          <BPReading systolic={c.index_systolic} diastolic={c.index_diastolic} size="xl" />
          <p className="text-sm text-muted">{t("result.needsChecking")}</p>
        </div>
      </Card>

      {c.urgent && c.emergency_advice && (
        <Notice tone="due" title={t("result.emergencyTitle")}>
          {c.emergency_advice.text}
        </Notice>
      )}

      <NextStepCard />
      {!c.next_step?.acting_role || c.next_step.acting_role !== "patient" ? (
        <p className="text-muted">{t("home.nothingFromYou")}</p>
      ) : null}

      {links.length > 0 && (
        <section aria-labelledby="more-title" className="flex flex-col gap-2">
          <h2 id="more-title" className="m-0 text-base font-semibold">
            {t("home.moreTitle")}
          </h2>
          {links.map((l) => (
            <Link key={l.key} to={l.to} className={rowLink}>
              <span className="font-medium">{t(`home.links.${l.key}`)}</span>
              <span className="text-sm text-muted">{t(`home.linksHint.${l.key}`)}</span>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}

function ClosedSummary() {
  const { t, i18n } = useTranslation("patient");
  const c = useCurrentCase();
  const thread = useThread(i18n.language);
  const msg = latestMessage(thread.data, "case_closed_summary");
  const closure = c.closure;
  return (
    <div className="flex flex-col gap-4">
      <PageTitle>{t("closed.heading")}</PageTitle>
      <p className="text-muted">{t("closed.intro")}</p>
      <Card title={t("closed.outcome")}>
        <div className="flex flex-col gap-3">
          {closure && <p className="text-lg font-medium">{t(`closed.evidence.${closure.evidence_type}`)}</p>}
          {closure && (
            <p className="text-sm text-muted">
              <bdi>{t("closed.closedOn", { date: formatDate(closure.closed_at, i18n.language) })}</bdi>
              {closure.closed_by_person ? ` · ${t("closed.by", { name: closure.closed_by_person.name })}` : ""}
            </p>
          )}
          <p>{t("closed.note")}</p>
        </div>
      </Card>
      {msg && (
        <Card title={t("closed.summaryTitle")}>
          <p className="m-0 whitespace-pre-line leading-relaxed">{msg.text}</p>
        </Card>
      )}
    </div>
  );
}
