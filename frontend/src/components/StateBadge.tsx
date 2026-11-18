import { useTranslation } from "react-i18next";
import type { CaseState } from "@/api/types";
import type { Tone } from "@/lib/cx";
import { Badge } from "./Badge";

const tones: Record<CaseState, Tone> = {
  RESULT_ISSUED: "info",
  NOTIFIED: "info",
  ACKNOWLEDGED: "info",
  CONFIRMED: "info",
  REFERRED: "info",
  APPOINTMENT_BOOKED: "accent",
  IN_CARE: "accent",
  CLOSED: "neutral",
};

export function useStateLabel() {
  const { t } = useTranslation();
  return (state: string) => t(`states.${state}`, { defaultValue: state });
}

export function StateBadge({ state, className }: { state: CaseState | string; className?: string }) {
  const label = useStateLabel();
  return (
    <Badge tone={tones[state as CaseState] ?? "neutral"} className={className}>
      {label(state)}
    </Badge>
  );
}
