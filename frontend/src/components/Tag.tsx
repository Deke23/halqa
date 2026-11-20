import type { HTMLAttributes, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";

export interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
}

/** Small outlined label for metadata such as a region or a channel. */
export function Tag({ className, children, ...rest }: TagProps) {
  return (
    <span
      className={cx("inline-flex items-center rounded-md border border-line-strong bg-surface px-1.5 py-0.5 text-xs font-medium leading-5 text-muted", className)}
      {...rest}
    >
      {children}
    </span>
  );
}

/**
 * The "Simulated" tag required on every screen that shows a simulated source
 * (IFHAS, Thiqa, Malaffi, SMS, WhatsApp, cover lines, simulation results). Dashed outline, so it reads as a demo aid.
 */
export function SimulatedTag({ className, label }: { className?: string; label?: string }) {
  const { t } = useTranslation();
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-md border border-dashed border-info-ink/55 bg-info-soft px-1.5 py-0.5 text-xs font-medium leading-5 text-info-ink",
        className,
      )}
    >
      <span aria-hidden="true" className="inline-block size-1.5 rounded-full bg-info-ink" />
      {label ?? t("simulated")}
    </span>
  );
}
