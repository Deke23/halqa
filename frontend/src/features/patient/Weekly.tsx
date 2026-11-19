import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, EmptyState, ErrorState, Loading, RadioGroup, Select, SimulatedTag, Field, useErrorText, useToast } from "@/components";
import type { components } from "@/api/schema";
import { formatDate, formatNumber } from "@/lib/format";
import { currentWeek, latestMessage, pastWeeks, useDiary, usePatientAction, useThread, type Feedback, type PlanWeekOut } from "./api";
import { Notice, PageTitle, useCurrentCase } from "./ui";

type Barrier = components["schemas"]["Barrier"];
const BARRIERS: Barrier[] = ["TIME", "COST", "NOT_SURE_HOW", "FELT_UNWELL", "WORK_SCHEDULE", "OTHER"];

export default function Weekly() {
  const { t } = useTranslation("patient");
  const c = useCurrentCase();
  const loc = useLocation();

  useEffect(() => {
    if (loc.hash === "#diary") document.getElementById("diary")?.scrollIntoView({ block: "start" });
  }, [loc.hash]);

  const week = currentWeek(c.plan);
  const history = pastWeeks(c.plan);
  const lifestyle = c.consents.find((x) => x.purpose === "lifestyle_programme");
  const paused = c.state === "IN_CARE" && lifestyle !== undefined && !lifestyle.granted;

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>{t("weekly.heading")}</PageTitle>
      <p className="text-muted">{t("weekly.intro")}</p>
      {paused && <Paused />}
      {!paused && !week && history.length === 0 ? <Notice>{t("weekly.notYet")}</Notice> : null}
      {!paused && week && <ThisWeek week={week} lastWeek={history[0]} />}
      <History weeks={history} />
      <Diary />
    </div>
  );
}

function Paused() {
  const { t } = useTranslation("patient");
  const toast = useToast();
  const errorText = useErrorText();
  const c = useCurrentCase();
  const act = usePatientAction(c.id);
  return (
    <Notice tone="info" title={t("weekly.pausedTitle")}>
      <p className="m-0">{t("weekly.pausedText")}</p>
      <div className="mt-3">
        <Button
          loading={act.isPending}
          onClick={() =>
            act.mutate(
              { action: "update_consent", payload: { purpose: "lifestyle_programme", granted: true, channel: null } },
              { onSuccess: () => toast.show(t("weekly.restarted")), onError: (e) => toast.show(errorText(e), "due") },
            )
          }
        >
          {t("weekly.restart")}
        </Button>
      </div>
    </Notice>
  );
}

function actionText(t: (k: string) => string, w: PlanWeekOut) {
  return { name: t(`weekly.action.${w.action_key}.name`), text: w.default_text };
}

function ThisWeek({ week, lastWeek }: { week: PlanWeekOut; lastWeek: PlanWeekOut | undefined }) {
  const { t, i18n } = useTranslation("patient");
  const toast = useToast();
  const errorText = useErrorText();
  const c = useCurrentCase();
  const act = usePatientAction(c.id);
  const thread = useThread(i18n.language);
  const [status, setStatus] = useState("");
  const [barrier, setBarrier] = useState("");
  const [larger, setLarger] = useState(false);
  const [tried, setTried] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const a = actionText((k) => t(k), week);
  const noBlameMsg = latestMessage(thread.data, "no_blame_checkin");
  const lapsedLast = lastWeek && lastWeek.status !== "done" && lastWeek.size !== week.size;

  const submit = () => {
    setTried(true);
    if (!status) return;
    act.mutate(
      {
        action: "plan_checkin",
        payload: {
          status,
          barrier: status !== "done" && barrier ? barrier : null,
          accept_larger: status === "done" && larger,
        },
      },
      {
        onSuccess: (d) => {
          setFeedback((d.feedback ?? null) as Feedback | null);
          setStatus("");
          setBarrier("");
          setLarger(false);
          setTried(false);
        },
        onError: (e) => toast.show(errorText(e), "due"),
      },
    );
  };

  return (
    <>
      {feedback && (
        <Notice tone="accent" title={feedback.code === "PLAN_SMALLER" ? t("weekly.noBlameTitle") : undefined}>
          {t(`weekly.feedback.${feedback.code}`, { defaultValue: t("weekly.feedback.PLAN_NEXT") })}
        </Notice>
      )}
      {!feedback && lapsedLast && (
        <Notice tone="accent" title={t("weekly.noBlameTitle")}>
          <p className="m-0">{t("weekly.noBlameLapsed")}</p>
          {noBlameMsg && <p className="m-0 mt-2 whitespace-pre-line text-sm">{noBlameMsg.text}</p>}
        </Notice>
      )}

      <Card title={t("weekly.thisWeek")} action={<Badge tone="accent">{t(`weekly.size.${week.size}`)}</Badge>}>
        <div className="flex flex-col gap-2">
          <p className="m-0 text-sm font-medium text-muted">{a.name}</p>
          <p className="m-0 text-lg font-semibold leading-snug">{a.text}</p>
        </div>
      </Card>

      <Card title={t("weekly.checkinTitle")}>
        <div className="flex flex-col gap-4">
          <RadioGroup
            name="checkin"
            legend={t("weekly.statusLegend")}
            value={status}
            onChange={setStatus}
            error={tried && !status ? t("weekly.needStatus") : undefined}
            options={(["done", "partly", "missed"] as const).map((s) => ({ value: s, label: t(`weekly.status.${s}`) }))}
          />
          {(status === "partly" || status === "missed") && (
            <Field label={t("weekly.barrierLabel")} optional>
              <Select
                value={barrier}
                onChange={(e) => setBarrier(e.target.value)}
                placeholder={t("weekly.barrierPlaceholder")}
                options={BARRIERS.map((b) => ({ value: b, label: t(`weekly.barrier.${b}`) }))}
              />
            </Field>
          )}
          {week.offered_larger && (
            <div className="flex flex-col gap-2 rounded-card bg-info-soft p-3 text-info-ink">
              <p className="m-0">{t("weekly.largerOffer")}</p>
              {status === "done" && (
                <label className="flex min-h-11 cursor-pointer items-center gap-3 font-medium">
                  <input
                    type="checkbox"
                    checked={larger}
                    onChange={(e) => setLarger(e.target.checked)}
                    className="size-5 accent-[var(--color-accent)]"
                  />
                  {t("weekly.largerAccept")}
                </label>
              )}
            </div>
          )}
          <Button size="lg" fullWidth loading={act.isPending} onClick={submit}>
            {t("weekly.submit")}
          </Button>
        </div>
      </Card>
    </>
  );
}

function History({ weeks }: { weeks: PlanWeekOut[] }) {
  const { t, i18n } = useTranslation("patient");
  return (
    <Card title={t("weekly.historyTitle")}>
      {weeks.length === 0 ? (
        <EmptyState description={t("weekly.historyEmpty")} />
      ) : (
        <ul className="m-0 flex list-none flex-col divide-y divide-line p-0">
          {weeks.map((w) => (
            <li key={w.week_index} className="flex items-start justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <p className="m-0 font-medium">{t(`weekly.action.${w.action_key}.name`)}</p>
                <p className="m-0 text-sm text-muted">
                  <bdi>{t("weekly.week", { n: w.week_index })}</bdi> · <bdi>{formatDate(w.starts_at, i18n.language)}</bdi> · {t(`weekly.size.${w.size}`)}
                </p>
              </div>
              <Badge tone={w.status === "done" ? "accent" : "neutral"}>{w.status ? t(`weekly.historyStatus.${w.status}`) : ""}</Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Diary() {
  const { t, i18n } = useTranslation("patient");
  const diary = useDiary();
  const days = diary.data ? [...diary.data.wearable_days].slice(-7) : [];
  const maxSteps = Math.max(1, ...days.map((d) => d.steps));
  return (
    <section id="diary" aria-labelledby="diary-title" className="scroll-mt-4">
      <Card
        title={<span id="diary-title">{t("weekly.diaryTitle")}</span>}
        action={<SimulatedTag />}
      >
        <div className="flex flex-col gap-3">
          <p className="m-0 text-sm text-muted">{t("weekly.diaryNote")}</p>
          {diary.isLoading ? (
            <Loading />
          ) : diary.error ? (
            <ErrorState error={diary.error} onRetry={() => void diary.refetch()} />
          ) : days.length === 0 ? (
            <EmptyState description={t("weekly.diaryEmpty")} />
          ) : (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {days.map((d) => (
                <li key={d.day} className="flex flex-col gap-1">
                  <div className="flex items-baseline justify-between gap-2 text-sm">
                    <span className="font-medium">
                      <bdi>{t("weekly.diaryDay", { n: d.day })}</bdi>
                    </span>
                    <span className="text-muted">
                      <bdi>
                        {t("weekly.steps", { n: formatNumber(d.steps, i18n.language) })} · {t("weekly.activeMinutes", { n: d.active_minutes })} ·{" "}
                        {t("weekly.sleepHours", { n: formatNumber(d.sleep_hours, i18n.language, { maximumFractionDigits: 1 }) })}
                      </bdi>
                    </span>
                  </div>
                  <div aria-hidden="true" className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
                    <div className="h-full rounded-full bg-accent" style={{ width: `${(d.steps / maxSteps) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </section>
  );
}
