import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";
import { personName, type I18nText } from "@/lib/i18nField";
import type { OwnerRole } from "@/api/types";

export interface OwnerChipProps {
  name?: string | null;
  /** Per-language names from the server. Preferred over `name` when present. */
  names?: I18nText;
  role?: OwnerRole | string | null;
  className?: string;
}

/** Accountable owner: a quiet "Name, Role" line, or an amber "No owner" chip when nobody is assigned. */
export function OwnerChip({ name, names, role, className }: OwnerChipProps) {
  const { t, i18n } = useTranslation();
  const shown = personName({ name, names }, i18n.language);
  const roleText = role && role !== "none" ? t(`roles.${role}`, { defaultValue: String(role) }) : "";
  if (!shown) {
    return (
      <span className={cx("inline-flex items-center gap-1.5 rounded-md bg-due-soft px-2 py-0.5 text-xs font-medium leading-5 text-due-ink", className)}>
        <span aria-hidden="true" className="inline-block size-1.5 shrink-0 rounded-full bg-current" />
        {t("owner.noOwner")}
        {roleText && <span className="font-normal">({roleText})</span>}
      </span>
    );
  }
  return (
    <span className={cx("inline-flex min-w-0 items-center gap-1.5 text-sm", className)}>
      <span aria-hidden="true" className="inline-block size-1.5 shrink-0 rounded-full bg-accent" />
      <span className="truncate font-medium">{shown}</span>
      {roleText && <span className="truncate text-muted">{roleText}</span>}
    </span>
  );
}
