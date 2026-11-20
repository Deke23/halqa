import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";

export interface StatCardProps {
  label: ReactNode;
  /** Already formatted value. Ignored when suppressed. */
  value?: ReactNode;
  /** Unit shown beside the value, for example "h" or "%". */
  unit?: ReactNode;
  /** Small text under the value, for example "p90 12 d". */
  sub?: ReactNode;
  /** Sample size, shown as n. */
  n?: number;
  /** Small-cell suppression: shows "fewer than 5" and hides the value. */
  suppressed?: boolean;
  className?: string;
}

export function StatCard({ label, value, unit, sub, n, suppressed, className }: StatCardProps) {
  const { t } = useTranslation();
  return (
    <div className={cx("rounded-card border border-line bg-surface p-4 sm:p-5", className)}>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-2 flex items-baseline gap-1.5">
        {suppressed ? (
          <span className="text-base font-medium text-muted">{t("fewerThan5")}</span>
        ) : (
          <>
            <span className="readout text-3xl font-semibold leading-none">{value}</span>
            {unit && <span className="text-sm text-muted">{unit}</span>}
          </>
        )}
      </p>
      {(sub || n !== undefined) && !suppressed && (
        <p className="mt-2 text-xs text-muted">
          {sub}
          {sub && n !== undefined ? " " : null}
          {n !== undefined && <bdi dir="ltr" className="readout">n = {n}</bdi>}
        </p>
      )}
    </div>
  );
}
