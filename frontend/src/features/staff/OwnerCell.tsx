import { OwnerChip } from "@/components";

/**
 * Server owner names already carry the role in brackets, for example "Dr Sara (family medicine)".
 * Show the role chip only when the name does not, or when there is no owner.
 */
export function OwnerCell({ name, role }: { name?: string | null; role?: string | null }) {
  return <OwnerChip name={name} role={name && name.includes("(") ? undefined : role} />;
}
