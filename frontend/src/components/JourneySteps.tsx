import { useTranslation } from "react-i18next";
import { CASE_STATES, type CaseState, type JourneyStepData } from "@/api/types";
import { formatDateTime } from "@/lib/format";
import { cx } from "@/lib/cx";

export interface JourneyStepsProps {
  /** The case state (last milestone reached). */
  currentState: CaseState;
  /** Optional per-step data from the case detail progress list, used for done timestamps. */
  steps?: JourneyStepData[];
  /** Override the step names, for example with plainer patient wording. Keyed by state. */
  labels?: Partial<Record<CaseState, string>>;
  className?: string;
}

/**
 * Vertical eight-step journey. Done steps are filled teal, the current step says "You are here",
 * later steps are quiet. No red anywhere, so it is safe on patient screens.
 */
export function JourneySteps({ currentState, steps, labels, className }: JourneyStepsProps) {
  const { t, i18n } = useTranslation();
  const currentIndex = Math.max(0, CASE_STATES.indexOf(currentState));
  const byState = new Map((steps ?? []).map((s) => [s.state, s]));

  return (
    <ol aria-label={t("journey.title")} className={cx("m-0 list-none p-0", className)}>
      {CASE_STATES.map((state, i) => {
        const isCurrent = i === currentIndex;
        const isDone = i < currentIndex;
        const doneAt = byState.get(state)?.done_at;
        const name = labels?.[state] ?? t(`states.${state}`);
        const last = i === CASE_STATES.length - 1;
        return (
          <li key={state} aria-current={isCurrent ? "step" : undefined} className="relative flex gap-3 pb-5 last:pb-0">
            {!last && (
              <span
                aria-hidden="true"
                className={cx("absolute start-[0.8rem] top-7 bottom-0 w-0.5", isDone ? "bg-accent" : "bg-line")}
              />
            )}
            <span
              aria-hidden="true"
              className={cx(
                "z-10 flex size-7 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold latin-digits",
                isDone && "border-accent bg-accent text-white",
                isCurrent && "border-accent bg-surface text-accent-ink ring-4 ring-accent-soft",
                !isDone && !isCurrent && "border-line bg-surface text-muted",
              )}
            >
              {isDone ? "✓" : i + 1}
            </span>
            <div className="min-w-0 pt-0.5">
              <p className={cx("font-medium", !isDone && !isCurrent && "text-muted")}>{name}</p>
              {isCurrent && (
                <p className="text-sm font-semibold text-accent-ink">{t("journey.youAreHere")}</p>
              )}
              {isDone && (
                <p className="text-sm text-muted">
                  {doneAt ? t("journey.doneAt", { when: formatDateTime(doneAt, i18n.language) }) : t("journey.done")}
                </p>
              )}
              {!isDone && !isCurrent && <p className="text-sm text-muted">{t("journey.upcoming")}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
