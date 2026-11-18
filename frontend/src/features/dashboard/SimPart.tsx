import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, Legend, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, EmptyState, ErrorState, Field, Loading, Select, SimulatedTag, Table, type Column } from "@/components";
import { useSimulation } from "./api";
import { useGroupLabel, useMeasureText } from "./format";
import { DAY_MEASURES, MEASURES, RATE_MEASURES, normSim, type MeasureDef, type Norm } from "./measures";
import { ParamsPanel } from "./ParamsPanel";
import { SensitivityPanel } from "./SensitivityPanel";
import type { Arm, RegionKey, SimCell } from "./types";

interface Props {
  split: string;
  region: RegionKey;
}

const ARMS: Arm[] = ["baseline", "with_loop"];
const BASE_FILL = "var(--color-line)";
const LOOP_FILL = "var(--color-accent)";

export function SimPart({ split, region }: Props) {
  const { t } = useTranslation("dashboard");
  const q = useSimulation();
  const text = useMeasureText();
  const groupLabel = useGroupLabel();
  const [groupSel, setGroupSel] = useState("");
  const [compare, setCompare] = useState("care_reached_rate");

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const data = q.data;
  if (!data?.available || !data.results) return <EmptyState description={t("sim.unavailable")} />;

  const regionRes = data.results[region];
  const groups = Object.keys(regionRes.with_loop[split] ?? {});
  const group = groups.includes(groupSel) ? groupSel : (groups[0] ?? "all");
  const cell = (arm: Arm, g: string): SimCell | undefined => regionRes[arm][split]?.[g];
  const get = (arm: Arm, g: string, name: string): Norm | undefined => normSim(cell(arm, g)?.[name]);
  const summary = data.metadata?.cohort_summary[region];
  const armName = (a: Arm) => t(`sim.arm.${a}`);

  const columns: Column<MeasureDef>[] = [
    {
      key: "m",
      header: t("measure"),
      cell: (m) => (
        <div>
          <p className="font-medium">{t(`measures.${m.name}.label`)}</p>
          <p className="max-w-xs text-xs text-muted">{t(`measures.${m.name}.help`)}</p>
        </div>
      ),
    },
    ...ARMS.map((a) => ({
      key: a,
      header: `${armName(a)} (${t("simulatedWord")})`,
      numeric: true,
      cell: (m: MeasureDef) => {
        const v = get(a, group, m.name);
        return (
          <span className="latin-digits">
            {text(m.kind, v)}
            {v && !v.suppressed && (
              <span className="block text-xs text-muted">
                {t("n")} = {v.n}
              </span>
            )}
          </span>
        );
      },
    })),
  ];

  const rateData = RATE_MEASURES.map((name) => ({
    name: t(`measures.${name}.label`),
    baseline: pct(get("baseline", group, name)),
    with_loop: pct(get("with_loop", group, name)),
  }));
  const dayData = DAY_MEASURES.map((name) => ({
    name: t(`measures.${name}.label`),
    baseline: med(get("baseline", group, name)),
    with_loop: med(get("with_loop", group, name)),
  }));

  const compareDef = MEASURES.find((m) => m.name === compare) ?? MEASURES[0]!;
  const compareData = groups.map((g) => ({
    name: groupLabel(split, g),
    baseline: scalar(compareDef, get("baseline", g, compare)),
    with_loop: scalar(compareDef, get("with_loop", g, compare)),
  }));
  const compareUnit =
    compareDef.kind === "rate"
      ? t("axis.percent")
      : compareDef.kind === "time_h"
        ? t("axis.hours")
        : compareDef.kind === "time_d"
          ? t("axis.days")
          : t("axis.score");

  // Unresolved results and why they dropped out of the pathway.
  const reasonKeys = Object.keys(reasonsOf(cell("with_loop", group)) ?? {});
  const reasonData = reasonKeys.map((k) => ({
    name: t(`simReasons.${k}`, { defaultValue: k }),
    baseline: reasonCount(cell("baseline", group), k),
    with_loop: reasonCount(cell("with_loop", group), k),
  }));
  const unresolvedBase = get("baseline", group, "unresolved_results");
  const unresolvedLoop = get("with_loop", group, "unresolved_results");

  return (
    <div className="flex flex-col gap-5">
      <div role="note" className="rounded-card border-2 border-info-ink bg-info-soft p-4 text-info-ink">
        <p className="flex flex-wrap items-center gap-2 font-semibold">
          <SimulatedTag />
          {t("sim.disclaimerTitle")}
        </p>
        <p className="mt-1">{t("sim.disclaimer")}</p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        {groups.length > 1 && (
          <Field label={t("sim.groupSelect")} className="w-64">
            <Select value={group} onChange={(e) => setGroupSel(e.target.value)} options={groups.map((g) => ({ value: g, label: groupLabel(split, g) }))} />
          </Field>
        )}
        {summary && (
          <p className="pb-2 text-sm text-muted">
            {t("sim.cohort", { people: summary.people, actionable: summary.actionable, severe: summary.severe })}
          </p>
        )}
      </div>

      <Card title={t("sim.compareTitle", { group: groupLabel(split, group) })} action={<SimulatedTag />}>
        <Table caption={t("sim.compareTitle", { group: groupLabel(split, group) })} columns={columns} rows={MEASURES} rowKey={(m) => m.name} />
        <p className="mt-2 text-xs text-muted">{t("sim.baselineNote")}</p>
      </Card>

      <div className="grid gap-5">
        <Card title={t("sim.ratesTitle")} action={<SimulatedTag />}>
          <Grouped data={rateData} yLabel={t("axis.percent")} caption={t("sim.ratesNote")} fmt={(v) => `${v}%`} armName={armName} />
        </Card>
        <Card title={t("sim.timesTitle")} action={<SimulatedTag />}>
          <Grouped data={dayData} yLabel={t("axis.days")} caption={t("sim.timesNote")} fmt={(v) => String(v)} armName={armName} />
        </Card>
      </div>

      {split !== "none" && (
        <Card title={t("sim.splitTitle", { split: t(`split.${split}`) })} action={<SimulatedTag />}>
          <Field label={t("sim.measureSelect")} className="mb-3 max-w-sm">
            <Select
              value={compare}
              onChange={(e) => setCompare(e.target.value)}
              options={MEASURES.filter((m) => m.kind !== "unresolved").map((m) => ({ value: m.name, label: t(`measures.${m.name}.label`) }))}
            />
          </Field>
          <Grouped data={compareData} yLabel={compareUnit} caption={t("sim.splitNote")} fmt={(v) => String(v)} armName={armName} />
        </Card>
      )}

      <Card title={t("sim.unresolvedTitle")} action={<SimulatedTag />}>
        <p className="mb-3 text-sm">
          {t("sim.unresolvedLine", {
            base: text("unresolved", unresolvedBase),
            loop: text("unresolved", unresolvedLoop),
          })}
        </p>
        {reasonData.length === 0 ? (
          <EmptyState description={t("sim.reasonsEmpty")} />
        ) : (
          <Grouped data={reasonData} yLabel={t("axis.people")} caption={t("sim.reasonsNote")} fmt={(v) => String(v)} armName={armName} />
        )}
        <p className="mt-2 text-xs text-muted">{t("sim.suppressedNote")}</p>
      </Card>

      <SensitivityPanel data={data} region={region} />
      <ParamsPanel data={data} />
      <div>
        <Badge tone="info">{t("sim.syntheticNote")}</Badge>
      </div>
    </div>
  );
}

function pct(m: Norm | undefined): number | null {
  return m && !m.suppressed && m.value != null ? Math.round(m.value * 1000) / 10 : null;
}
function med(m: Norm | undefined): number | null {
  return m && !m.suppressed && m.median != null ? m.median : null;
}
function scalar(def: MeasureDef, m: Norm | undefined): number | null {
  if (!m || m.suppressed) return null;
  if (def.kind === "rate") return pct(m);
  if (def.kind === "time_h" || def.kind === "time_d") return med(m);
  return m.value ?? null;
}
function reasonsOf(c: SimCell | undefined) {
  const m = c?.unresolved_results;
  return typeof m === "object" ? m.delay_reasons : undefined;
}
function reasonCount(c: SimCell | undefined, key: string): number | null {
  const r = reasonsOf(c)?.[key];
  return r && !r.suppressed ? r.count : null;
}

interface GroupedProps {
  data: Array<{ name: string; baseline: number | null; with_loop: number | null }>;
  yLabel: string;
  caption: string;
  fmt: (v: number) => string;
  armName: (a: Arm) => string;
}

/** Baseline in light grey with a dark outline, with-loop in teal. Values are printed on the bars. Null means suppressed or not measured. */
function Grouped({ data, yLabel, caption, fmt, armName }: GroupedProps) {
  const { t: tc } = useTranslation();
  return (
    <figure>
      <div className="h-72 w-full" role="img" aria-label={caption}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 18, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} height={56} />
            <YAxis tick={{ fontSize: 11 }} label={{ value: yLabel, angle: -90, position: "insideLeft", fontSize: 11 }} />
            <Tooltip formatter={(v) => (v == null ? tc("fewerThan5") : String(v))} />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={(v) => <span style={{ color: "var(--color-ink)" }}>{v}</span>} />
            <Bar dataKey="baseline" name={armName("baseline")} fill={BASE_FILL} stroke="var(--color-muted)" strokeWidth={1.5} isAnimationActive={false}>
              <LabelList dataKey="baseline" position="top" fontSize={10} formatter={(v: unknown) => (typeof v === "number" ? fmt(v) : "")} />
            </Bar>
            <Bar dataKey="with_loop" name={armName("with_loop")} fill={LOOP_FILL} isAnimationActive={false}>
              <LabelList dataKey="with_loop" position="top" fontSize={10} formatter={(v: unknown) => (typeof v === "number" ? fmt(v) : "")} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-muted">{caption}</figcaption>
    </figure>
  );
}
