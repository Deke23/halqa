import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, SimulatedTag, Table, type Column } from "@/components";
import { formatNumber, formatPercent } from "@/lib/format";
import type { RegionKey, SimResponse, SimSensitivityTop } from "./types";

/** One-way sensitivity: the three most influential assumptions scaled down and up by 20 percent. */
export function SensitivityPanel({ data, region }: { data: SimResponse; region: RegionKey }) {
  const { t, i18n } = useTranslation("dashboard");
  const s = data.sensitivity?.[region];
  if (!s) return null;
  const pp = (v: number) => `${formatNumber(v * 100, i18n.language, { maximumFractionDigits: 1 })} ${t("sens.points")}`;
  const num = (v: number) => formatNumber(v, i18n.language, { maximumFractionDigits: 3 });
  const name = (p: string) => p.replace("with_loop.", "").replace("baseline.", "");

  const columns: Column<SimSensitivityTop>[] = [
    { key: "p", header: t("sens.parameter"), cell: (r) => <span className="clinical">{r.parameter}</span> },
    {
      key: "range",
      header: t("sens.range"),
      numeric: true,
      cell: (r) => <span className="latin-digits">{num(r.low_value)} / {num(r.base_value)} / {num(r.high_value)}</span>,
    },
    { key: "low", header: t("sens.low"), numeric: true, cell: (r) => <span className="latin-digits">{pp(r.low.difference)}</span> },
    { key: "base", header: t("sens.base"), numeric: true, cell: (r) => <span className="latin-digits">{pp(r.base.difference)}</span> },
    { key: "high", header: t("sens.high"), numeric: true, cell: (r) => <span className="latin-digits">{pp(r.high.difference)}</span> },
  ];
  const ranking = s.ranking_top10.map((r) => ({ name: name(r.parameter), swing: Math.round(r.swing_in_care_rate_difference * 1000) / 10 }));

  return (
    <Card title={t("sens.title")} action={<SimulatedTag />}>
      <p className="mb-3 text-sm">{t("sens.intro")}</p>
      <Table caption={t("sens.title")} columns={columns} rows={s.top3} rowKey={(r) => r.parameter} />
      <p className="mt-2 text-xs text-muted">{t("sens.tableNote", { base: formatPercent(s.top3[0]?.base.baseline_care_reached_rate ?? 0, i18n.language) })}</p>
      <figure className="mt-4">
        <div className="h-80 w-full" role="img" aria-label={t("sens.chartLabel")}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={ranking} layout="vertical" margin={{ top: 8, right: 36, bottom: 24, left: 8 }}>
              <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11 }} label={{ value: t("sens.axis"), position: "insideBottom", offset: -12, fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={190} tick={{ fontSize: 10 }} interval={0} />
              <Tooltip />
              <Bar dataKey="swing" name={t("sens.swing")} fill="var(--color-accent)" isAnimationActive={false}>
                <LabelList dataKey="swing" position="right" fontSize={10} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <figcaption className="mt-1 text-xs text-muted">{t("sens.method")}</figcaption>
      </figure>
    </Card>
  );
}
