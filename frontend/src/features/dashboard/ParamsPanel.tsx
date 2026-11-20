import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Card, Field, Select, SimulatedTag, Table, type Column } from "@/components";
import type { SimParam, SimResponse } from "./types";

function show(v: unknown): string {
  if (typeof v === "number" || typeof v === "string" || typeof v === "boolean") return String(v);
  return JSON.stringify(v);
}

/** "What this is based on": every parameter with its value, source and kind. */
export function ParamsPanel({ data }: { data: SimResponse }) {
  const { t, i18n } = useTranslation("dashboard");
  const english = i18n.language === "en";
  const sourceText = (src: string) =>
    src === "Assumption" ? t("params.kinds.assumption") : src.startsWith("Simple app") ? t("params.published.simple_bangladesh") : src;
  const [kind, setKind] = useState("all");
  const params = data.parameters ?? [];
  const rows = params.filter((p) => kind === "all" || p.kind === kind);
  const published = params.filter((p) => p.kind === "published").length;

  const columns: Column<SimParam>[] = [
    { key: "name", header: t("params.name"), cell: (p) => <span className="clinical break-all">{p.name}</span> },
    { key: "value", header: t("params.value"), cell: (p) => <span className="clinical break-all">{show(p.value)}</span> },
    { key: "unit", header: t("params.unit"), cell: (p) => t(`params.units.${p.unit.replace(/ /g, "_")}`, { defaultValue: p.unit }) },
    { key: "kind", header: t("params.kind"), cell: (p) => <Badge tone={p.kind === "published" ? "accent" : "due"}>{t(`params.kinds.${p.kind}`)}</Badge> },
    { key: "source", header: t("params.source"), cell: (p) => <span className="text-xs">{sourceText(p.source)}</span> },
    ...(english ? [{ key: "why", header: t("params.rationale"), cell: (p: SimParam) => <span className="text-xs text-muted">{p.rationale ?? ""}</span> }] : []),
  ];

  return (
    <Card title={t("basedOn")} action={<SimulatedTag />}>
      <p className="mb-2 text-sm">{t("params.intro", { total: params.length, published, assumptions: params.length - published })}</p>
      <details className="mb-3 text-sm">
        <summary className="cursor-pointer font-medium text-accent-ink">{t("params.sources")}</summary>
        <ul className="mt-2 list-disc ps-5">
          {Object.entries(data.published_sources ?? {}).map(([k, v]) => (
            <li key={k}>{english ? v : t(`params.published.${k}`, { defaultValue: v })}</li>
          ))}
        </ul>
        <p className="mt-1 text-xs text-muted">{t("params.sourcesNote")}</p>
      </details>
      {!english && <p className="mb-2 text-xs text-muted">{t("params.rationaleEnglish")}</p>}
      <Field label={t("params.filter")} className="mb-3 max-w-xs">
        <Select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          options={[
            { value: "all", label: t("params.all") },
            { value: "published", label: t("params.kinds.published") },
            { value: "assumption", label: t("params.kinds.assumption") },
          ]}
        />
      </Field>
      <div className="max-h-[32rem] overflow-y-auto rounded-card">
        <Table caption={t("basedOn")} columns={columns} rows={rows} rowKey={(p) => p.name} />
      </div>
    </Card>
  );
}
