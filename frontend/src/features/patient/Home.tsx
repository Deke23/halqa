import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LoopRing, OwnerChip } from "@/components";
import { formatDate } from "@/lib/format";
import { personName, pickText } from "@/lib/i18nField";
import { latestMessage, useThread } from "./api";
import { Notice, PageTitle, Panel, Readout, i18nOf, firstName, primaryLink, screenFor, useCurrentCase } from "./ui";

const rowLink =
  "flex min-h-14 flex-col justify-center gap-0.5 border-t border-line px-1 py-3 first:border-t-0 hover:bg-surface-2";

export default function Home() {
  const { t, i18n } = useTranslation("patient");
  const c = useCurrentCase();
  const state = c.state;
  const closed = state === "CLOSED";
  const reached = c.progress.filter((p) => p.reached).length;
  const step = c.next_step;
  const patientActs = step?.acting_role === "patient";
  const target = screenFor(step?.label_key);
  const known = step ? t(`next.${step.label_key}.title`, { defaultValue: "" }) !== "" : false;
  const key = known && step ? step.label_key : "default";
  const stepLabel = t("home.stepOf", { n: closed ? 8 : Math.max(1, reached), total: 8 });

  const afterAck = state !== "RESULT_ISSUED" && state !== "NOTIFIED";
  const afterConfirm = ["CONFIRMED", "REFERRED", "APPOINTMENT_BOOKED", "IN_CARE", "CLOSED"].includes(state);
  const links: { to: string; key: string }[] = [];
  if (state === "NOTIFIED") links.push({ to: "/patient/understand", key: "understand" });
  if (afterAck && !closed) links.push({ to: "/patient/confirm", key: "confirm" });
  if (afterConfirm && !closed) links.push({ to: "/patient/visit", key: "visit" });
  if (state === "IN_CARE") {
    links.push({ to: "/patient/weekly", key: "weekly" });
    links.push({ to: "/patient/weekly#diary", key: "diary" });
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <PageTitle>{t("home.hello", { name: firstName(personName(c.patient)) })}</PageTitle>
        {closed && <p className="m-0 text-muted">{t("closed.intro")}</p>}
      </div>

      <section className="rise-in flex flex-col items-center gap-4 rounded-card border border-line bg-surface px-5 py-6 text-center">
        <LoopRing size={184} thickness={14} reached={closed ? 8 : reached} closed={closed} label={stepLabel}>
          <span className="flex flex-col items-center leading-none">
            <Readout className="text-[2.15rem] font-semibold">
              {c.index_systolic}/{c.index_diastolic}
            </Readout>
            <span className="mt-1.5 text-xs text-muted">{t("units.mmHg", { ns: "common" })}</span>
          </span>
        </LoopRing>

        <div className="flex flex-col items-center gap-1">
          <p className="m-0 text-sm text-muted">{stepLabel}</p>
          <p className="m-0 text-lg font-semibold">{t(`journey.states.${state}`)}</p>
          <Link to="/patient/result" className="mt-1 text-sm font-medium text-accent-ink underline underline-offset-4">
            {t("home.seeResult")}
          </Link>
        </div>

        {closed ? (
          <ClosedOutcome />
        ) : (
          <div className="flex w-full flex-col gap-3 border-t border-line pt-4 text-start">
            <div>
              <p className="m-0 text-lg font-semibold">{t(`next.${key}.title`)}</p>
              <p className="m-0 mt-1 text-sm text-muted">{t(`next.${key}.text`)}</p>
            </div>
            {step && (
              <div className="m-0 flex flex-col gap-1 text-sm text-muted">
                <OwnerChip name={personName(step.owner_person)} role={pickText(step.owner_person?.roles, "") || step.owner_role} />
                <span>
                  {t("next.by")} <bdi className="font-medium text-ink">{formatDate(step.due_at, i18n.language)}</bdi>
                </span>
              </div>
            )}
            {patientActs && target ? (
              <Link to={target} className={primaryLink}>
                {t(`next.${key}.title`)}
              </Link>
            ) : (
              <p className="m-0 rounded-control bg-accent-soft px-4 py-3 text-accent-ink">{t("home.nothingFromYou")}</p>
            )}
          </div>
        )}
      </section>

      {c.urgent && c.emergency_advice && (
        <Notice tone="due" title={t("result.emergencyTitle")}>
          {i18nOf(c.emergency_advice, "text")}
        </Notice>
      )}

      {links.length > 0 && (
        <Panel title={t("home.moreTitle")} className="!p-4">
          <div className="flex flex-col">
          {links.map((l) => (
            <Link key={l.key} to={l.to} className={rowLink}>
              <span className="font-medium">{t(`home.links.${l.key}`)}</span>
              <span className="text-sm text-muted">{t(`home.linksHint.${l.key}`)}</span>
            </Link>
          ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function ClosedOutcome() {
  const { t, i18n } = useTranslation("patient");
  const c = useCurrentCase();
  const thread = useThread(i18n.language);
  const msg = latestMessage(thread.data, "case_closed_summary");
  const closure = c.closure;
  return (
    <div className="flex w-full flex-col gap-3 border-t border-line pt-5 text-start">
      <p className="m-0 text-sm text-muted">{t("closed.outcome")}</p>
      {closure && <p className="m-0 text-lg font-semibold">{t(`closed.evidence.${closure.evidence_type}`)}</p>}
      {closure && (
        <p className="m-0 text-sm text-muted">
          {t("closed.closedOn", { date: formatDate(closure.closed_at, i18n.language) })}
          {closure.closed_by_person ? ` · ${t("closed.by", { name: personName(closure.closed_by_person) })}` : ""}
        </p>
      )}
      {msg && <p className="m-0 whitespace-pre-line leading-relaxed">{msg.text}</p>}
      <p className="m-0 text-sm text-muted">{t("closed.note")}</p>
    </div>
  );
}
