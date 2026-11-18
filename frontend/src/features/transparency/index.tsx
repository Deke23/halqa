import { useTranslation } from "react-i18next";
import { useConfig } from "@/api/hooks";
import { Badge, Card, ErrorState, Loading, SimulatedTag, Table, type Column } from "@/components";
import { APP_NAME } from "@/config";
import { formatNumber } from "@/lib/format";
import type { ConfigOut } from "@/features/staff/types";

type Entry = ConfigOut["entries"][number];
type Tpl = { id: string; version: number | string; purpose: string; languages: string[]; required_slots: string[]; channel_limits: Record<string, unknown> };

const SECTIONS = ["thresholds", "service_levels", "escalation", "unreachable_protocol", "closure", "teach_back", "lifestyle_plan"] as const;

/** Route /transparency, public. Everything about thresholds comes from GET /api/config. */
export default function Transparency() {
  const { t, i18n } = useTranslation("staff");
  const q = useConfig<ConfigOut>();

  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const cfg = q.data;
  const minNote = Number(cfg.entries.find((e) => e.section === "closure" && e.key === "note_min_chars")?.value ?? 10);

  const unitText = (u: string) => t(`transparency.units.${u}`, { defaultValue: u });
  const entryColumns: Column<Entry>[] = [
    { key: "key", header: t("transparency.setting"), cell: (e) => <span className="font-medium">{t(`transparency.keys.${e.key}`, { defaultValue: e.key.replace(/_/g, " ") })}</span> },
    {
      key: "value",
      header: t("transparency.value"),
      cell: (e) => (
        <span className="clinical">
          {typeof e.value === "number" ? formatNumber(e.value, i18n.language) : String(e.value)} {unitText(e.unit)}
        </span>
      ),
    },
    { key: "basis", header: t("transparency.basis"), cell: (e) => <span className="text-xs">{e.basis}</span> },
    {
      key: "status",
      header: t("transparency.status"),
      cell: (e) => <Badge tone="due">{e.status === "placeholder_pending_clinician_signoff" ? t("transparency.placeholder") : e.status}</Badge>,
    },
  ];

  const templates = cfg.templates as unknown as Tpl[];
  const tplColumns: Column<Tpl>[] = [
    { key: "id", header: t("transparency.template"), cell: (x) => <span className="clinical break-all">{x.id}</span> },
    { key: "v", header: t("transparency.version"), cell: (x) => <span className="clinical">{String(x.version)}</span> },
    { key: "p", header: t("transparency.purpose"), cell: (x) => <span className="text-xs">{x.purpose}</span> },
    { key: "l", header: t("transparency.languages"), cell: (x) => x.languages.map((l) => t(`language.${l}`)).join(", ") },
    { key: "s", header: t("transparency.slots"), cell: (x) => <span className="clinical text-xs">{x.required_slots.join(", ")}</span> },
  ];

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold">{t("transparency.title", { app: APP_NAME })}</h1>
        <p className="mt-2 max-w-prose text-sm text-muted">{t("transparency.intro")}</p>
      </header>

      <div role="note" className="rounded-card border-2 border-due bg-due-soft p-4 text-due-ink">
        <p className="font-semibold">{t("transparency.placeholderTitle")}</p>
        <p>{t("transparency.placeholderBody")}</p>
      </div>

      <Card title={t("transparency.rulesTitle")}>
        <ol className="flex list-decimal flex-col gap-3 ps-5 text-sm">
          <li>
            <span className="font-semibold">{t("transparency.rule1Title")}</span> {t("transparency.rule1")}
          </li>
          <li>
            <span className="font-semibold">{t("transparency.rule2Title")}</span> {t("transparency.rule2", { min: minNote })}
          </li>
          <li>
            <span className="font-semibold">{t("transparency.rule3Title")}</span> {t("transparency.rule3")}
          </li>
          <li>
            <span className="font-semibold">{t("transparency.rule4Title")}</span> {t("transparency.rule4")}
          </li>
        </ol>
      </Card>

      <Card title={t("transparency.closureTitle")}>
        <p className="text-sm">{t("transparency.closureBody", { min: minNote })}</p>
        <p className="mt-3 text-sm font-medium">{t("transparency.evidenceTypes")}</p>
        <ul className="mt-1 flex flex-wrap gap-2">
          {cfg.closure_evidence_types.map((x) => (
            <li key={x}>
              <Badge tone="info">{t(`evidence.${x}`, { defaultValue: x })}</Badge>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={t("transparency.aiTitle")}>
        <ul className="flex list-disc flex-col gap-2 ps-5 text-sm">
          <li>{t("transparency.ai1")}</li>
          <li>{t("transparency.ai2")}</li>
          <li>{t("transparency.ai3")}</li>
          <li>{t("transparency.ai4")}</li>
          <li>{t("transparency.ai5")}</li>
        </ul>
      </Card>

      {SECTIONS.map((s) => {
        const rows = cfg.entries.filter((e) => e.section === s);
        if (rows.length === 0) return null;
        return (
          <section key={s} aria-labelledby={`cfg-${s}`}>
            <h2 id={`cfg-${s}`} className="mb-2 text-lg font-semibold">
              {t(`transparency.sections.${s}`)}
            </h2>
            <p className="mb-2 text-sm text-muted">{t(`transparency.sectionHints.${s}`)}</p>
            <Table caption={t(`transparency.sections.${s}`)} columns={entryColumns} rows={rows} rowKey={(e) => `${e.section}.${e.key}`} />
          </section>
        );
      })}

      <section aria-labelledby="cfg-templates">
        <h2 id="cfg-templates" className="mb-2 text-lg font-semibold">
          {t("transparency.templatesTitle")}
        </h2>
        <p className="mb-2 text-sm text-muted">{t("transparency.templatesIntro", { count: templates.length })}</p>
        <Table caption={t("transparency.templatesTitle")} columns={tplColumns} rows={templates} rowKey={(x) => x.id} />
      </section>

      <Card title={t("transparency.dataTitle")} action={<SimulatedTag />}>
        <ul className="flex list-disc flex-col gap-2 ps-5 text-sm">
          <li>{t("transparency.data1")}</li>
          <li>{t("transparency.data2")}</li>
          <li>{t("transparency.data3")}</li>
          <li>{t("transparency.data4")}</li>
        </ul>
      </Card>
    </div>
  );
}
