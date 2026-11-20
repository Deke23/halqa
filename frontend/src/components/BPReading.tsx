import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";

export interface BPReadingProps {
  systolic: number;
  diastolic: number;
  /** Hide the unit when space is tight. */
  hideUnit?: boolean;
  size?: "sm" | "md" | "xl" | "hero";
  className?: string;
}

const sizes = { sm: "text-base", md: "text-xl", xl: "text-4xl", hero: "text-6xl" } as const;

/**
 * Formats a blood pressure as 152/96 mmHg. The numbers are Latin digits and left to right,
 * isolated so they stay correct inside Arabic text.
 */
export function BPReading({ systolic, diastolic, hideUnit, size = "md", className }: BPReadingProps) {
  const { t } = useTranslation();
  return (
    <span className={cx("inline-flex items-baseline gap-1.5 whitespace-nowrap", className)}>
      <bdi dir="ltr" className={cx("bp font-semibold leading-none", sizes[size])}>
        {String(Math.round(systolic))}/{String(Math.round(diastolic))}
      </bdi>
      {!hideUnit && <span className="whitespace-nowrap text-sm text-muted">{t("units.mmHg")}</span>}
    </span>
  );
}
