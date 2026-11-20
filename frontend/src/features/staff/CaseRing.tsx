import { useTranslation } from "react-i18next";
import { LoopRing } from "@/components";
import { CASE_STATES } from "@/api/types";

interface Props {
  /** The case state, the last milestone reached. */
  state: string;
  urgent?: boolean;
  size?: number;
  /** Show "N of 8" inside the ring. */
  readout?: boolean;
}

/** Steps reached for a case state: the state is the last milestone, so the index plus one. */
export function stepsReached(state: string): number {
  const i = (CASE_STATES as readonly string[]).indexOf(state);
  return i < 0 ? 0 : i + 1;
}

/** The loop ring for a case, with its accessible label. */
export function CaseRing({ state, urgent = false, size = 30, readout = false }: Props) {
  const { t } = useTranslation("staff");
  const closed = state === "CLOSED";
  const reached = stepsReached(state);
  const label = closed ? t("ring.closed") : t("ring.label", { n: reached, total: 8 });
  return (
    <LoopRing reached={reached} closed={closed} urgent={urgent && !closed} size={size} label={label}>
      {readout && (
        <span className="readout text-sm font-semibold leading-none">
          {closed ? "8" : reached}
          <span className="text-muted">/8</span>
        </span>
      )}
    </LoopRing>
  );
}
