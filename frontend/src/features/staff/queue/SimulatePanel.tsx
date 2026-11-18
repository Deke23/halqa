import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, Field, Input, SimulatedTag, useErrorText, useToast } from "@/components";
import { useSimulateResult } from "../api";

interface Props {
  region: "AUH" | "YDE";
  /** Called with the new case id (when a case opened) and whether it is severe. */
  onLanded: (caseId: number, severe: boolean) => void;
}

/** Posts a fake incoming result to the intake endpoint. A severe reading lands at the top of the urgent tab. */
export function SimulatePanel({ region, onLanded }: Props) {
  const { t } = useTranslation("staff");
  const toast = useToast();
  const errorText = useErrorText();
  const sim = useSimulateResult();
  const [sys, setSys] = useState("150");
  const [dia, setDia] = useState("95");
  const [error, setError] = useState<string | null>(null);

  function send(systolic: number, diastolic: number) {
    setError(null);
    sim.mutate(
      { region, reading: { systolic, diastolic } },
      {
        onSuccess: (res) => {
          if (res.opened && res.case_id != null) {
            onLanded(res.case_id, res.severity === "SEVERE");
            toast.show(t(res.severity === "SEVERE" ? "simulate.landedSevere" : "simulate.landed", { id: res.case_id }));
          } else {
            toast.show(t("simulate.notActionable", { reason: res.reason }), "due");
          }
        },
        onError: (e) => setError(errorText(e)),
      },
    );
  }

  function sendCustom() {
    const s = Number(sys);
    const d = Number(dia);
    if (!Number.isInteger(s) || !Number.isInteger(d) || s < 60 || s > 260 || d < 30 || d > 160) {
      setError(t("simulate.range"));
      return;
    }
    send(s, d);
  }

  return (
    <Card title={t("simulate.title")} action={<SimulatedTag />}>
      <p className="mb-3 text-sm text-muted">{t("simulate.intro")}</p>
      <div className="flex flex-wrap items-end gap-3">
        <Button variant="danger" loading={sim.isPending} onClick={() => send(185, 115)}>
          {t("simulate.severe")}
        </Button>
        <span className="pb-2 text-sm text-muted">{t("simulate.or")}</span>
        <Field label={t("simulate.systolic")} className="w-28">
          <Input inputMode="numeric" value={sys} onChange={(e) => setSys(e.target.value)} />
        </Field>
        <Field label={t("simulate.diastolic")} className="w-28">
          <Input inputMode="numeric" value={dia} onChange={(e) => setDia(e.target.value)} />
        </Field>
        <Button variant="secondary" loading={sim.isPending} onClick={sendCustom}>
          {t("simulate.custom")}
        </Button>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm font-medium text-due-ink">
          {error}
        </p>
      )}
    </Card>
  );
}
