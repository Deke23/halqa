import { useTranslation } from "react-i18next";

interface Props {
  label: string;
  help?: string;
  /** Big number, already formatted. */
  value?: string;
  unit?: string;
  /** Second line, for example the 90th percentile. */
  sub?: string;
  n?: number;
  suppressed?: boolean;
  notMeasured?: boolean;
}

/** Stat card with a large mono readout. A suppressed cell never shows a number. */
export function ReadoutCard({ label, help, value, unit, sub, n, suppressed, notMeasured }: Props) {
  const { t } = useTranslation();
  const { t: td } = useTranslation("dashboard");
  return (
    <div className="flex flex-col gap-1 rounded-card border border-line bg-surface p-4">
      <p className="text-sm font-medium">{label}</p>
      <p className="flex items-baseline gap-1.5">
        {suppressed ? (
          <span className="text-base font-medium text-muted">{t("fewerThan5")}</span>
        ) : notMeasured ? (
          <span className="text-base font-medium text-muted">{td("notMeasured")}</span>
        ) : (
          <>
            <span className="readout text-3xl font-semibold leading-none">{value}</span>
            {unit && <span className="text-sm text-muted">{unit}</span>}
          </>
        )}
      </p>
      {!suppressed && !notMeasured && (sub || n !== undefined) && (
        <p className="text-xs text-muted">
          {sub && <span className="readout">{sub}</span>}
          {sub && n !== undefined ? " · " : ""}
          {n !== undefined && <span className="readout">n = {n}</span>}
        </p>
      )}
      {help && <p className="mt-1 text-xs text-muted">{help}</p>}
    </div>
  );
}
