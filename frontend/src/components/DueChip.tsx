import { useTranslation } from "react-i18next";
import { cx, toneClasses, type Tone } from "@/lib/cx";
import { dueInfo } from "@/lib/format";
import { useDemoNow } from "@/api/hooks";

export interface DueChipProps {
  /** ISO timestamp of the due date. */
  dueAt?: string | null;
  /** Server flag. When given it wins over the local calculation. */
  overdue?: boolean;
  /** Override the clock (tests, kitchen sink). Defaults to the demo clock. */
  now?: Date;
  /**
   * staff: overdue is clay red. patient: overdue is amber, never red.
   * Red is reserved for clinical urgency on staff screens.
   */
  audience?: "staff" | "patient";
  className?: string;
}

/** Hours to the shortest readable text: hours below 48, otherwise days. */
export function useDurationText() {
  const { t } = useTranslation();
  return (hours: number): string => {
    if (hours < 48) return t("units.hour", { count: Math.max(1, Math.round(hours)) });
    const days = Math.floor(hours / 24);
    return t("units.day", { count: days });
  };
}

export function DueChip({ dueAt, overdue, now, audience = "staff", className }: DueChipProps) {
  const { t } = useTranslation();
  const demoNow = useDemoNow();
  const durationText = useDurationText();
  const info = dueInfo(dueAt, now ?? demoNow);
  const status = overdue === true ? "overdue" : overdue === false && info.status === "overdue" ? "on_time" : info.status;

  let tone: Tone = "neutral";
  let text = t("due.noDate");
  if (status === "on_time") {
    tone = "accent";
    text = t("due.onTime");
  } else if (status === "due_soon") {
    tone = "due";
    text = t("due.dueIn", { value: durationText(info.hours) });
  } else if (status === "overdue") {
    tone = audience === "staff" ? "urgent" : "due";
    text = t("due.overdueBy", { value: durationText(Math.max(info.hours, 1)) });
  }

  return (
    <span
      className={cx("inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium leading-5", toneClasses[tone], className)}
    >
      <span aria-hidden="true" className="inline-block size-1.5 shrink-0 rounded-full bg-current" />
      {text}
    </span>
  );
}
