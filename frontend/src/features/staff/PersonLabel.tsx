import { OwnerChip } from "@/components";
import { useLabels } from "./labels";
import type { PersonRef } from "./types";

/** "Name, job title" with the job title translated. */
export function usePersonText() {
  const labels = useLabels();
  return (p: PersonRef | null | undefined): string => (p ? `${p.name}, ${labels.roleTitle(p.role)}` : "");
}

/** Owner chip from a PersonRef. No owner shows the amber "No owner" chip with the owner role. */
export function OwnerCell({ person, role }: { person: PersonRef | null | undefined; role?: string | null }) {
  const labels = useLabels();
  if (!person) return <OwnerChip name={null} role={role} />;
  return (
    <span className="inline-flex flex-col text-sm">
      <span className="font-medium">{person.name}</span>
      <span className="text-xs text-muted">{labels.roleTitle(person.role)}</span>
    </span>
  );
}
