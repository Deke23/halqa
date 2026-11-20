import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, EmptyState, ErrorState, Loading, Table, type Column } from "@/components";
import { COLOR, WrapTick } from "./charts";
import { ReadoutCard } from "./ReadoutCard";
import { formatDateTime } from "@/lib/format";
import { pickText } from "@/lib/i18nField";
import { useLive } from "./api";
import { useGroupLabel, useMeasureParts, useMeasureText } from "./format";
import { DAY_MEASURES, MEASURES, normLive, type MeasureDef, type Norm } from "./measures";

interface Props {
  split: string;
  region: string;
}

export function LivePart({ split, region }: Props) {
  const { t, i18n } = useTranslation("dashboard");
  const q = useLive(split, region);
  const text = useMeasureText();
  const parts = useMeasureParts();
  const groupLabel = useGroupLabel();

  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const data = q.data;
  if (!data || data.groups.length === 0) return <EmptyState description={t("live.empty")} />;

  const defs = MEASURES.filter((m) => !m.simOnly);
  const first = data.groups[0]!;
  const byName = (gKey: string) => {
    const g = data.groups.find((x) => x.key === gKey);
    return (name: string): Norm | undefined => normLive(g?.measures.find((m) => m.name === name));
  };
  const firstGet = byName(first.key);

  const columns: Column<MeasureDef>[] = [
    { key: "measure", header: t("measure"), cell: (m) => <MeasureName name={m.name} /> },
    ...data.groups.map((g) => ({
      key: g.key,
      header: (
        <span>{pickText(g.label_i18n, groupLabel(split, g.key))}</span>
      ),
      numeric: true,
      cell: (m: MeasureDef) => {
        const v = byName(g.key)(m.name);
        return (
          <span className="latin-digits">
            {text(m.kind, v)}
            {v && !v.suppressed && <span className="block text-xs text-muted">{t("n")} = {v.n}</span>}
          </span>
        );
      },
    })),
  ];

  const timing = DAY_MEASURES.map((name) => {
    const v = firstGet(name);
    return { name: t(`measures.${name}.label`), median: v && !v.suppressed ? v.median ?? null : null };
  }).filter((r) => r.median !== null);

  const unresolved = firstGet("unresolved_results");
  const reasons = (unresolved?.reasons ?? []).filter((r) => !r.suppressed && r.n != null).map((r) => ({ name: t(`liveReasons.${r.key}`, { defaultValue: r.key }), n: r.n }));

  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm font-medium">{t("live.research")}</p>
      <p className="text-sm text-muted">
        {t("live.intro", { when: formatDateTime(data.generated_at, i18n.language), min: data.min_cell_size })}
      </p>

      {split === "none" && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {defs.map((m) => {
            const v = firstGet(m.name);
            const p = parts(m.kind, v);
            return (
              <ReadoutCard
                key={m.name}
                label={t(`measures.${m.name}.label`)}
                help={t(`measures.${m.name}.help`)}
                value={p.value}
                unit={p.unit}
                sub={p.sub}
                n={v?.n}
                suppressed={p.suppressed}
                notMeasured={p.notMeasured}
              />
            );
          })}
        </div>
      )}

      {split !== "none" && (
        <Table caption={t("live.tableCaption")} columns={columns} rows={defs} rowKey={(m) => m.name} />
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={t("live.timingTitle")} action={<Badge>{t("live.liveTag")}</Badge>}>
          {timing.length === 0 ? (
            <EmptyState description={t("live.timingEmpty")} />
          ) : (
            <BarsOne data={timing} xKey="name" yKey="median" yLabel={t("axis.days")} fill={COLOR.loop} caption={t("live.timingNote", { group: groupLabel(split, first.key) })} />
          )}
        </Card>
        <Card title={t("live.reasonsTitle")} action={<Badge>{t("live.liveTag")}</Badge>}>
          {reasons.length === 0 ? (
            <EmptyState description={t("live.reasonsEmpty")} />
          ) : (
            <BarsOne data={reasons} xKey="name" yKey="n" yLabel={t("axis.cases")} fill={COLOR.delay} caption={t("live.reasonsNote", { group: groupLabel(split, first.key) })} />
          )}
        </Card>
      </div>
    </div>
  );
}

function MeasureName({ name }: { name: string }) {
  const { t } = useTranslation("dashboard");
  return (
    <div>
      <p className="font-medium">{t(`measures.${name}.label`)}</p>
      <p className="max-w-xs text-xs text-muted">{t(`measures.${name}.help`)}</p>
    </div>
  );
}

function BarsOne<T extends Record<string, unknown>>({ data, xKey, yKey, yLabel, caption, fill }: { data: T[]; xKey: string; yKey: string; yLabel: string; caption: string; fill: string }) {
  return (
    <figure>
      <div className="h-60 w-full" role="img" aria-label={caption}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 16, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid stroke={COLOR.grid} strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey={xKey} tick={<WrapTick />} interval={0} height={64} />
            <YAxis tick={{ fontSize: 11 }} label={{ value: yLabel, angle: -90, position: "insideLeft", fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey={yKey} fill={fill} isAnimationActive={false}>
              <LabelList dataKey={yKey} position="top" fontSize={11} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-muted">{caption}</figcaption>
    </figure>
  );
}
