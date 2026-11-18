import type { TFunction } from "i18next";
import { formatDateTime } from "@/lib/format";
import type { CaseDetail } from "./types";

/**
 * One extra line for a queue row, read from the case detail:
 * the rejection reason, the escalation reason, or the last contact attempt.
 */
export function detailReason(d: CaseDetail, t: TFunction, lng: string): string | null {
  if (d.flags.rejected && d.referral?.rejection_reason) {
    return t("queue.rejectedBy", { name: d.referral.to_name ?? t("queue.receiver"), reason: d.referral.rejection_reason });
  }
  const events = [...d.timeline].reverse();
  if (d.flags.escalated) {
    const esc = events.find((e) => e.type === "ESCALATED");
    if (esc) return t("queue.escalatedReason", { reason: esc.reason ?? t("queue.escalatedDefault") });
  }
  const contact = events.find((e) => e.type === "MESSAGE_SENT" || e.type === "UNREACHABLE_STEP");
  if (contact) return t("queue.lastContact", { when: formatDateTime(contact.at, lng) });
  return null;
}
