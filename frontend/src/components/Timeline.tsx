import { useTranslation } from "react-i18next";
import type { TimelineEvent } from "@/api/types";
import { formatDateTime } from "@/lib/format";
import { cx } from "@/lib/cx";
import { personName } from "@/lib/i18nField";

export interface TimelineProps {
  events: TimelineEvent[];
  /** Map an event type to display text. Default: "CASE_VIEWED" becomes "Case viewed". */
  eventLabel?: (event: TimelineEvent) => string;
  /** Newest first by default, matching an audit view. */
  order?: "newest_first" | "oldest_first";
  className?: string;
}

function humanise(type: string): string {
  const s = type.toLowerCase().replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Audit events as a list. The case timeline in the UI is the append-only CaseEvent log. */
export function Timeline({ events, eventLabel, order = "newest_first", className }: TimelineProps) {
  const { t, i18n } = useTranslation();
  const sorted = [...events].sort((a, b) => (order === "newest_first" ? -1 : 1) * a.at.localeCompare(b.at));
  return (
    <ol aria-label={t("timeline.title")} className={cx("m-0 list-none p-0", className)}>
      {sorted.map((ev, i) => {
        const actor = personName({ name: ev.actor_name, names: (ev as { actor_names?: Record<string, string> }).actor_names }, i18n.language) || (ev.actor_role ? t(`roles.${ev.actor_role}`, { defaultValue: ev.actor_role }) : t("timeline.system"));
        return (
          <li key={ev.id} className="relative flex gap-3 pb-4 last:pb-0">
            {i < sorted.length - 1 && <span aria-hidden="true" className="absolute start-[0.3rem] top-3 bottom-0 w-px bg-line" />}
            <span aria-hidden="true" className={cx("z-10 mt-1.5 size-2.5 shrink-0 rounded-full", i === (order === "newest_first" ? 0 : sorted.length - 1) ? "bg-accent ring-4 ring-accent-soft" : "bg-line-strong")} />
            <div className="min-w-0">
              <p className="text-sm font-medium">{eventLabel ? eventLabel(ev) : humanise(ev.type)}</p>
              <p className="text-xs text-muted">
                <time dateTime={ev.at} className="readout">{formatDateTime(ev.at, i18n.language)}</time> {t("timeline.by", { actor })}
              </p>
              {ev.reason && <p className="mt-1 text-sm">{ev.reason}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
