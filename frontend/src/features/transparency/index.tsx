import { useTranslation } from "react-i18next";
import { useConfig } from "@/api/hooks";
import { Badge, Card, ErrorState, Loading, SimulatedTag, Table, type Column } from "@/components";
import { APP_NAME, APP_NAME_AR } from "@/config";
import { formatNumber } from "@/lib/format";
import { pickText, type I18nText } from "@/lib/i18nField";
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
    { key: "key", header: t("transparency.setting"), cell: (e) => <span className="font-medium">{pickText(e.label_i18n, t(`transparency.keys.${e.key}`, { defaultValue: e.key.replace(/_/g, " ") }))}</span> },
    {
      key: "value",
      header: t("transparency.value"),
      cell: (e) => (
        <span>
          <span className="readout">{typeof e.value === "number" ? formatNumber(e.value, i18n.language) : String(e.value)}</span>{" "}
          {pickText(e.unit_i18n, unitText(e.unit))}
        </span>
      ),
    },
    { key: "basis", header: t("transparency.basis"), cell: (e) => <span className="text-xs">{pickText(e.basis_i18n, e.basis)}</span> },
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
    { key: "p", header: t("transparency.purpose"), cell: (x) => <span className="text-xs">{pickText((x as unknown as { purpose_i18n?: I18nText }).purpose_i18n, x.purpose)}</span> },
    { key: "l", header: t("transparency.languages"), cell: (x) => x.languages.map((l) => t(`language.${l}`)).join(", ") },
    { key: "s", header: t("transparency.slots"), cell: (x) => <span className="clinical text-xs">{x.required_slots.join(", ")}</span> },
  ];

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold">{t("transparency.title", { app: i18n.language === "ar" ? APP_NAME_AR : APP_NAME })}</h1>
        <p className="mt-2 max-w-prose text-sm text-muted">{t("transparency.intro")}</p>
      </header>

      <section aria-labelledby="three-rules" className="grid gap-4 md:grid-cols-3">
        <h2 id="three-rules" className="sr-only">
          {t("transparency.rulesTitle")}
        </h2>
        <article className="rise-in flex flex-col gap-2 rounded-card border border-line bg-surface p-5">
          <p className="readout text-sm text-accent-ink">1</p>
          <h3 className="text-base font-semibold">{t("transparency.rule1Title")}</h3>
          <p className="text-sm">{t("transparency.rule1")}</p>
          <p className="text-sm text-muted">{t("transparency.ai5")}</p>
          <details className="mt-1 text-sm">
            <summary className="cursor-pointer font-medium text-accent-ink">{t("transparency.aiTitle")}</summary>
            <ul className="mt-2 flex list-disc flex-col gap-1.5 ps-5 text-muted">
              <li>{t("transparency.ai1")}</li>
              <li>{t("transparency.ai2")}</li>
              <li>{t("transparency.ai3")}</li>
              <li>{t("transparency.ai4")}</li>
              <li>{t("transparency.ai5")}</li>
            </ul>
          </details>
        </article>
        <article className="rise-in flex flex-col gap-2 rounded-card border border-line bg-surface p-5">
          <p className="readout text-sm text-accent-ink">2</p>
          <h3 className="text-base font-semibold">{t("transparency.rule2Title")}</h3>
          <p className="text-sm">{t("transparency.rule2", { min: minNote })}</p>
          <p className="mt-1 text-xs font-medium text-muted">{t("transparency.evidenceTypes")}</p>
          <ul className="flex flex-wrap gap-1.5">
            {cfg.closure_evidence_types.map((x) => (
              <li key={x}>
                <Badge tone="info">{pickText(cfg.closure_evidence_labels.find((l) => l.code === x)?.label_i18n, t(`evidence.${x}`, { defaultValue: x }))}</Badge>
              </li>
            ))}
          </ul>
        </article>
        <article className="rise-in flex flex-col gap-2 rounded-card border border-due bg-due-soft p-5 text-due-ink">
          <p className="readout text-sm">3</p>
          <h3 className="text-base font-semibold">{t("transparency.placeholderTitle")}</h3>
          <p className="text-sm">{t("transparency.placeholderBody")}</p>
        </article>
      </section>

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

      <Card title={t("transparency.regionsTitle")}>
        <p className="mb-2 text-sm">{t("transparency.regionsBody")}</p>
        <ul className="flex flex-col gap-1 text-sm">
          {cfg.regions.map((r) => (
            <li key={r.region}>
              <span className="font-medium">{pickText(r.name_i18n, r.name)}</span>: <span className="clinical">{r.timezone}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-muted">{t(cfg.demo_mode ? "transparency.demoOn" : "transparency.demoOff")}</p>
      </Card>

      <Card title={t("transparency.dataTitle")} action={<SimulatedTag />}>
        <ul className="flex list-disc flex-col gap-2 ps-5 text-sm">
          <li>{t("transparency.data1")}</li>
          <li>{t("transparency.rule3Title")} {t("transparency.rule3")}</li>
          <li>{t("transparency.rule4Title")} {t("transparency.rule4")}</li>
          <li>{t("transparency.data2")}</li>
          <li>{t("transparency.data3")}</li>
          <li>{t("transparency.data4")}</li>
        </ul>
      </Card>
    </div>
  );
}
