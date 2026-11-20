import { useTranslation } from "react-i18next";
import { Badge } from "@/components";
import { personName } from "@/lib/i18nField";
import { useLabels } from "./labels";
import type { PersonRef } from "./types";

/** "Name, job title" in the interface language. */
export function usePersonText() {
  const labels = useLabels();
  return (p: PersonRef | null | undefined): string => (p ? `${personName(p)}, ${labels.roleTitle(p.role, p)}` : "");
}

/** Owner from a PersonRef. No owner shows the amber "No owner" chip with the owner role. */
export function OwnerCell({ person, role }: { person: PersonRef | null | undefined; role?: string | null }) {
  const labels = useLabels();
  const { t } = useTranslation("common");
  if (!person)
    return (
      <span className="inline-flex flex-col items-start gap-0.5 leading-tight">
        <Badge tone="due" className="whitespace-nowrap">{t("owner.noOwner")}</Badge>
        {role && role !== "none" && <span className="text-xs text-muted">{t(`roles.${role}`, { defaultValue: role })}</span>}
      </span>
    );
  return (
    <span className="inline-flex flex-col text-sm leading-tight">
      <span className="font-medium">{personName(person)}</span>
      <span className="text-xs text-muted">{labels.roleTitle(person.role, person)}</span>
    </span>
  );
}
