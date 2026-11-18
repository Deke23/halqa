import { useTranslation } from "react-i18next";
import { Card, JourneySteps } from "@/components";
import { CASE_STATES, type CaseState } from "@/api/types";
import { NextStepCard, PageTitle, useCurrentCase } from "./ui";

export default function Journey() {
  const { t } = useTranslation("patient");
  const c = useCurrentCase();
  const labels = Object.fromEntries(CASE_STATES.map((s) => [s, t(`journey.states.${s}`)])) as Record<CaseState, string>;
  const steps = c.progress.map((p) => ({ state: p.state, done_at: p.reached_at, current: p.current }));
  // The shell marks steps before the current one as done. The backend's `reached` flag is the same idea.
  const current = (c.progress.find((p) => p.current)?.state ?? c.state) as CaseState;
  return (
    <div className="flex flex-col gap-4">
      <PageTitle>{t("journey.heading")}</PageTitle>
      <p className="text-muted">{t("journey.intro")}</p>
      <Card>
        <JourneySteps currentState={current} steps={steps} labels={labels} />
      </Card>
      <h2 className="m-0 text-base font-semibold">{t("journey.whoTitle")}</h2>
      <NextStepCard compact />
      <p className="text-sm text-muted">{t("journey.closedNote")}</p>
    </div>
  );
}
