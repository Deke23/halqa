import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BPReading, Card, Loading, SimulatedTag, Tag } from "@/components";
import { formatDate } from "@/lib/format";
import { latestMessage, useThread } from "./api";
import { BulletList, NextStepCard, Notice, PageTitle, useCurrentCase } from "./ui";

export default function Result() {
  const { t, i18n } = useTranslation("patient");
  const c = useCurrentCase();
  const thread = useThread(i18n.language);
  const severe = c.severity === "SEVERE";
  const message = latestMessage(thread.data, severe ? "result_severe" : "result_raised");
  const first = c.readings[0];
  const sourceKey = c.source_system;
  const simulated = sourceKey === "IFHAS_SCREENING";
  const means = t("result.means", { returnObjects: true }) as string[];
  const notMeans = t("result.notMeans", { returnObjects: true }) as string[];

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>{t("result.heading")}</PageTitle>

      <Card>
        <div className="flex flex-col items-start gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Tag>{t(`result.source.${sourceKey}`, { defaultValue: t("result.source.OTHER") })}</Tag>
            {simulated && <SimulatedTag />}
          </div>
          <BPReading systolic={c.index_systolic} diastolic={c.index_diastolic} size="xl" />
          <p className="text-sm text-muted">{t("result.mmHgNote")}</p>
          {first && (
            <p className="text-sm text-muted">
              <bdi>{t("result.takenOn", { date: formatDate(first.taken_at, i18n.language) })}</bdi>
            </p>
          )}
          <p className="font-medium">{t("result.needsChecking")}</p>
        </div>
      </Card>

      {c.emergency_advice && (
        <Notice tone="due" title={t("result.emergencyTitle")}>
          {c.emergency_advice.text}
        </Notice>
      )}

      <Card title={t("result.meansTitle")}>
        <BulletList items={means} />
      </Card>

      <Card title={t("result.notMeansTitle")}>
        <BulletList items={notMeans} />
      </Card>

      <Card title={t("result.urgencyTitle")}>
        {severe ? (
          <p>{t("result.urgencySevere")}</p>
        ) : (
          <p>
            <bdi>{t("result.urgencyRaised", { date: formatDate(c.next_step?.due_at, i18n.language) })}</bdi>
          </p>
        )}
      </Card>

      <NextStepCard compact />

      {c.state === "NOTIFIED" ? (
        <Link
          to="/patient/understand"
          className="inline-flex min-h-11 items-center justify-center rounded-lg bg-accent px-4 py-2 font-semibold text-white hover:bg-accent-strong"
        >
          {t("result.toUnderstand")}
        </Link>
      ) : (
        c.state !== "RESULT_ISSUED" && <p className="text-sm text-muted">{t("result.alreadyUnderstood")}</p>
      )}

      <Card title={t("result.messageTitle")}>
        {thread.isLoading ? (
          <Loading />
        ) : message ? (
          <blockquote className="m-0 whitespace-pre-line border-s-4 border-accent ps-3 leading-relaxed">{message.text}</blockquote>
        ) : (
          <p className="text-muted">{t("messages.empty")}</p>
        )}
      </Card>
    </div>
  );
}
