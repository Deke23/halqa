import type { HTMLAttributes, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";

export interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
}

/** Small outlined label. Use for metadata such as a region or a channel. */
export function Tag({ className, children, ...rest }: TagProps) {
  return (
    <span
      className={cx("inline-flex items-center rounded border border-line bg-surface px-1.5 py-0.5 text-xs font-medium text-muted", className)}
      {...rest}
    >
      {children}
    </span>
  );
}

/**
 * The "Simulated" tag required on every screen that shows a simulated source
 * (IFHAS, Thiqa, Malaffi, SMS, WhatsApp, cover lines, simulation results).
 */
export function SimulatedTag({ className, label }: { className?: string; label?: string }) {
  const { t } = useTranslation();
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded border border-dashed border-info-ink/60 bg-info-soft px-1.5 py-0.5 text-xs font-semibold text-info-ink",
        className,
      )}
    >
      <span aria-hidden="true" className="inline-block size-1.5 rounded-full bg-info-ink" />
      {label ?? t("simulated")}
    </span>
  );
}
