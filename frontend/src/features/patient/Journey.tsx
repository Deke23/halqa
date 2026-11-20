import { useTranslation } from "react-i18next";
import { JourneySteps, LoopRing } from "@/components";
import { CASE_STATES, type CaseState } from "@/api/types";
import { NextStepCard, PageTitle, Panel, useCurrentCase } from "./ui";

export default function Journey() {
  const { t } = useTranslation("patient");
  const c = useCurrentCase();
  const labels = Object.fromEntries(CASE_STATES.map((s) => [s, t(`journey.states.${s}`)])) as Record<CaseState, string>;
  const steps = c.progress.map((p) => ({ state: p.state, done_at: p.reached_at, current: p.current }));
  const current = (c.progress.find((p) => p.current)?.state ?? c.state) as CaseState;
  const reached = c.progress.filter((p) => p.reached).length;
  const closed = c.state === "CLOSED";
  const stepLabel = t("home.stepOf", { n: closed ? 8 : Math.max(1, reached), total: 8 });
  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-4">
        <LoopRing size={40} thickness={5} reached={closed ? 8 : reached} closed={closed} label={stepLabel} />
        <div className="min-w-0">
          <PageTitle>{t("journey.heading")}</PageTitle>
          <p className="m-0 text-sm text-muted">{stepLabel}</p>
        </div>
      </div>
      <p className="m-0 text-muted">{t("journey.intro")}</p>
      <Panel>
        <JourneySteps currentState={current} steps={steps} labels={labels} />
      </Panel>
      <NextStepCard compact />
      <p className="m-0 text-sm text-muted">{t("journey.closedNote")}</p>
    </div>
  );
}
