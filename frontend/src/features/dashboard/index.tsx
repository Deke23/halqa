import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Field, Select, SimulatedTag } from "@/components";
import { LivePart } from "./LivePart";
import { SimPart } from "./SimPart";
import { SPLITS, type RegionKey } from "./types";

/** Route /dashboard. Two separate parts: live measures from this demo database, and the simulation file. */
export default function Dashboard() {
  const { t } = useTranslation("dashboard");
  const [split, setSplit] = useState("none");
  const [liveRegion, setLiveRegion] = useState("");
  const [simRegion, setSimRegion] = useState<RegionKey>("AUH");

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="max-w-prose text-sm text-muted">{t("intro")}</p>
        <div className="mt-2 max-w-xs">
          <Field label={t("splitLabel")} hint={t("splitHint")}>
            <Select value={split} onChange={(e) => setSplit(e.target.value)} options={SPLITS.map((s) => ({ value: s, label: t(`split.${s}`) }))} />
          </Field>
        </div>
      </header>

      <section aria-labelledby="live-heading" className="flex flex-col gap-4 rounded-card border-2 border-accent p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="live-heading" className="flex items-center gap-2 text-xl font-semibold">
            {t("live.title")}
            <Badge tone="accent">{t("live.tag")}</Badge>
          </h2>
          <Field label={t("regionLabel")} className="w-56">
            <Select
              value={liveRegion}
              onChange={(e) => setLiveRegion(e.target.value)}
              options={[
                { value: "", label: t("regionAll") },
                { value: "AUH", label: t("regionAUH") },
                { value: "YDE", label: t("regionYDE") },
              ]}
            />
          </Field>
        </div>
        <p className="text-sm text-muted">{t("live.scope")}</p>
        <LivePart split={split} region={liveRegion} />
      </section>

      <section aria-labelledby="sim-heading" className="flex flex-col gap-4 rounded-card border-2 border-dashed border-info-ink p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="sim-heading" className="flex items-center gap-2 text-xl font-semibold">
            {t("sim.title")}
            <SimulatedTag />
          </h2>
          <Field label={t("regionLabel")} className="w-56">
            <Select
              value={simRegion}
              onChange={(e) => setSimRegion(e.target.value as RegionKey)}
              options={[
                { value: "AUH", label: t("regionAUH") },
                { value: "YDE", label: t("regionYDE") },
              ]}
            />
          </Field>
        </div>
        <SimPart split={split} region={simRegion} />
      </section>
    </div>
  );
}
