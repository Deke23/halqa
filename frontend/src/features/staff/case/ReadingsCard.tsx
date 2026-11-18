import { useTranslation } from "react-i18next";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useConfig } from "@/api/hooks";
import { Badge, BPReading, Card, EmptyState } from "@/components";
import { formatDate, formatDateTime } from "@/lib/format";
import { useLabels } from "../labels";
import type { CaseDetail, ConfigOut } from "../types";

function entry(cfg: ConfigOut | undefined, key: string): number | undefined {
  const e = cfg?.entries.find((x) => x.key === key);
  return e ? Number(e.value) : undefined;
}

export function ReadingsCard({ detail }: { detail: CaseDetail }) {
  const { t, i18n } = useTranslation("staff");
  const labels = useLabels();
  const config = useConfig<ConfigOut>();
  const readings = [...detail.readings].sort((a, b) => a.taken_at.localeCompare(b.taken_at));
  const conf = detail.confirmation;
  const usesAbpm = conf?.method === "ABPM";
  const sysT = entry(config.data, usesAbpm ? "abpm_daytime_systolic" : "hbpm_systolic");
  const diaT = entry(config.data, usesAbpm ? "abpm_daytime_diastolic" : "hbpm_diastolic");
  const data = readings.map((r, i) => ({
    i,
    when: formatDate(r.taken_at, i18n.language),
    systolic: r.systolic,
    diastolic: r.diastolic,
  }));
  const sysName = t("readings.systolic");
  const diaName = t("readings.diastolic");

  const statusTone = conf?.status === "CONFIRMED_RAISED" ? "due" : conf?.status === "NOT_CONFIRMED" ? "accent" : "neutral";

  return (
    <Card title={t("readings.title")} action={<Badge>{readings.length}</Badge>}>
      {readings.length === 0 ? (
        <EmptyState description={t("readings.empty")} />
      ) : (
        <>
          <div className="h-56 w-full" role="img" aria-label={t("readings.chartLabel", { count: readings.length })}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 8, right: 30, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" />
                <XAxis dataKey="when" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                <YAxis
                  domain={[50, "dataMax + 10"]}
                  tick={{ fontSize: 11 }}
                  label={{ value: t("readings.axisY"), angle: -90, position: "insideLeft", fontSize: 11 }}
                />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {sysT !== undefined && (
                  <ReferenceLine y={sysT} stroke="var(--color-muted)" strokeDasharray="2 4" label={{ value: String(sysT), fontSize: 10, position: "right" }} />
                )}
                {diaT !== undefined && (
                  <ReferenceLine y={diaT} stroke="var(--color-muted)" strokeDasharray="2 4" label={{ value: String(diaT), fontSize: 10, position: "right" }} />
                )}
                <Line type="monotone" dataKey="systolic" name={sysName} stroke="var(--color-accent)" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                <Line
                  type="monotone"
                  dataKey="diastolic"
                  name={diaName}
                  stroke="var(--color-info-ink)"
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  dot={{ r: 3, strokeWidth: 2, fill: "var(--color-surface)" }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-1 text-xs text-muted">{t("readings.chartNote", { sys: sysT ?? "", dia: diaT ?? "" })}</p>

          <details className="mt-3">
            <summary className="cursor-pointer text-sm font-medium text-accent-ink">{t("readings.showTable")}</summary>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-start text-sm">
                <caption className="sr-only">{t("readings.title")}</caption>
                <thead>
                  <tr className="text-muted">
                    <th scope="col" className="py-1 pe-3 text-start font-medium">{t("readings.when")}</th>
                    <th scope="col" className="py-1 pe-3 text-start font-medium">{t("readings.value")}</th>
                    <th scope="col" className="py-1 pe-3 text-start font-medium">{t("readings.pulse")}</th>
                    <th scope="col" className="py-1 text-start font-medium">{t("readings.source")}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...readings].reverse().map((r) => (
                    <tr key={r.id} className="border-t border-line">
                      <td className="py-1 pe-3">{formatDateTime(r.taken_at, i18n.language)}</td>
                      <td className="py-1 pe-3"><BPReading systolic={r.systolic} diastolic={r.diastolic} size="sm" hideUnit /></td>
                      <td className="py-1 pe-3 latin-digits">{r.pulse ?? ""}</td>
                      <td className="py-1">{labels.source(r.source)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}

      <section className="mt-4 rounded-lg border border-line bg-surface-2 p-3" aria-labelledby="confirm-eval">
        <h3 id="confirm-eval" className="text-sm font-semibold">{t("confirmation.title")}</h3>
        {!conf || !conf.method ? (
          <p className="mt-1 text-sm text-muted">{t("confirmation.notStarted")}</p>
        ) : (
          <div className="mt-2 flex flex-col gap-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="info">{t(`method.${conf.method}`)}</Badge>
              {conf.status && <Badge tone={statusTone}>{t(`confirmation.status.${conf.status}`)}</Badge>}
            </div>
            {conf.average_systolic != null && conf.average_diastolic != null ? (
              <p>
                {t("confirmation.average")}{" "}
                <BPReading systolic={Math.round(conf.average_systolic)} diastolic={Math.round(conf.average_diastolic)} size="sm" />
              </p>
            ) : (
              <p className="text-muted">{t("confirmation.noAverage")}</p>
            )}
            <p className="text-muted">
              {t("confirmation.days", {
                counted: conf.days_counted,
                enough: conf.days_with_enough_readings,
                required: conf.days_required,
                used: conf.readings_used,
              })}
            </p>
            <p>
              {t("confirmation.threshold", { sys: sysT ?? "", dia: diaT ?? "" })}{" "}
              <Badge tone="due">{t("placeholder")}</Badge>
            </p>
            <p className="text-xs text-muted">{t("confirmation.placeholderNote")}</p>
          </div>
        )}
      </section>
    </Card>
  );
}
