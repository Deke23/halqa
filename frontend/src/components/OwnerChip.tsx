import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";
import type { OwnerRole } from "@/api/types";

export interface OwnerChipProps {
  name?: string | null;
  role?: OwnerRole | string | null;
  className?: string;
}

/** Accountable owner: "Name, Role", or "No owner" in amber when nobody is assigned. */
export function OwnerChip({ name, role, className }: OwnerChipProps) {
  const { t } = useTranslation();
  if (!name) {
    return (
      <span className={cx("inline-flex items-center rounded-full bg-due-soft px-2.5 py-0.5 text-xs font-semibold text-due-ink", className)}>
        {t("owner.noOwner")}
        {role && role !== "none" ? <span className="ms-1 font-normal">({t(`roles.${role}`, { defaultValue: String(role) })})</span> : null}
      </span>
    );
  }
  return (
    <span className={cx("inline-flex items-center gap-1.5 text-sm", className)}>
      <span className="font-medium">{name}</span>
      {role && <span className="text-muted">{t(`roles.${role}`, { defaultValue: String(role) })}</span>}
    </span>
  );
}
