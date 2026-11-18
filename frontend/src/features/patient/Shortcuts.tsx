import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Tag, useErrorText, useToast } from "@/components";
import { actAs, advanceClockAs, replyAs, slotsAs, useDiary, type PatientCase } from "./api";
import { plainName } from "./ui";

type Flow = "auh" | "yde";
type Key = "review" | "referral" | "book" | "visit" | "skip" | "close" | "sampleWeek";

const STAFF = {
  auh: { review: "clinician_pcp", refer: "clinician_pcp", accept: "clinician_specialist", book: "patient_auh", visit: "clinician_specialist", close: "clinician_pcp", clock: "coordinator_auh" },
  yde: { review: "clinician_yde", refer: "clinician_yde", accept: "specialist_yde", book: "nurse_yde", visit: "specialist_yde", close: "clinician_yde", clock: "nurse_yde" },
} as const;

const SKIP_HOURS = 8 * 24; // one week plus the one day of grace the plan rules allow before a week counts as lapsed
const SAMPLE_STEP_HOURS = 12;

/**
 * A small, collapsed panel of demo aids. Each care team button signs in as the right staff persona in the
 * background and calls the real action endpoint, so the transition is real and audited under that role.
 * Nothing here changes state on the client.
 */
export function Shortcuts({ c, flow }: { c: PatientCase; flow: Flow }) {
  const { t } = useTranslation("patient");
  const toast = useToast();
  const errorText = useErrorText();
  const qc = useQueryClient();
  const diary = useDiary();
  const [busy, setBusy] = useState<Key | null>(null);
  const who = STAFF[flow];

  const state = c.state;
  const avail: Record<Key, boolean> = {
    review: state === "ACKNOWLEDGED" && c.confirmation?.status === "CONFIRMED_RAISED",
    referral: state === "CONFIRMED" || (state === "REFERRED" && c.referral_status === "PENDING"),
    book: state === "REFERRED" && c.referral_status === "ACCEPTED",
    visit: state === "APPOINTMENT_BOOKED",
    skip: state === "IN_CARE",
    close: state === "IN_CARE",
    sampleWeek: state === "ACKNOWLEDGED",
  };

  const run = async (key: Key) => {
    setBusy(key);
    try {
      if (key === "review") {
        const r = await actAs(who.review, c.id, "review_confirmation", {
          outcome: "CONFIRMED",
          note: t("shortcuts.note.review", { lng: "en" }),
        });
        toast.show(t("shortcuts.did.review", { who: plainName(r.who) }));
      } else if (key === "referral") {
        if (state === "CONFIRMED") {
          const r = await actAs(who.refer, c.id, "refer", {
            to_service: "hypertension_clinic",
            reason: t("shortcuts.note.refer", { lng: "en" }),
          });
          toast.show(t("shortcuts.did.refer", { who: plainName(r.who) }));
        }
        const a = await actAs(who.accept, c.id, "accept_referral", {});
        toast.show(t("shortcuts.did.accept", { who: plainName(a.who) }));
      } else if (key === "book") {
        const slots = await slotsAs(who.book, c.id);
        const first = slots[0];
        if (!first) throw { status: 404, code: "NO_SLOTS", message: t("visit.slotsEmpty") };
        const r = await actAs(who.book, c.id, "book_appointment", { slot_id: first.id });
        toast.show(t("shortcuts.did.book", { who: plainName(r.who) }));
      } else if (key === "visit") {
        const r = await actAs(who.visit, c.id, "record_visit", { outcome: "TREATMENT_STARTED" });
        toast.show(t("shortcuts.did.visit", { who: plainName(r.who) }));
      } else if (key === "close") {
        const r = await actAs(who.close, c.id, "close", {
          evidence_type: "OTHER_CLINICAL_DECISION",
          decision_note: t("shortcuts.note.close", { lng: "en" }),
        });
        toast.show(t("shortcuts.did.close", { who: plainName(r.who) }));
      } else if (key === "skip") {
        await advanceClockAs(who.clock, SKIP_HOURS);
        toast.show(t("shortcuts.did.skip"));
      } else if (key === "sampleWeek") {
        // Reads the sample series from the diary endpoint and sends each reading as a text message,
        // moving the demo clock 12 hours between messages so the readings land on different days.
        const sample = diary.data?.hbpm_sample ?? [];
        const picks: string[] = [];
        for (const day of [...new Set(sample.map((r) => r.day))]) {
          const rows = sample.filter((r) => r.day === day);
          const morning = rows[0];
          const evening = rows[rows.length - 1];
          if (morning) picks.push(`${morning.systolic}/${morning.diastolic}`);
          if (evening && evening !== morning) picks.push(`${evening.systolic}/${evening.diastolic}`);
        }
        for (const text of picks) {
          await replyAs(text);
          await advanceClockAs(who.clock, SAMPLE_STEP_HOURS);
        }
        toast.show(t("shortcuts.did.sampleWeek"));
      }
      await qc.invalidateQueries();
    } catch (e) {
      toast.show(t("shortcuts.failed", { message: errorText(e) }), "due");
      await qc.invalidateQueries();
    } finally {
      setBusy(null);
    }
  };

  const keys: Key[] = flow === "auh" ? ["review", "referral", "visit", "skip", "close"] : ["sampleWeek", "review", "referral", "book", "visit", "skip", "close"];

  return (
    <details className="rounded-card border border-dashed border-info-ink/60 bg-info-soft text-info-ink">
      <summary className="flex min-h-11 cursor-pointer items-center gap-2 px-4 py-2 font-semibold">
        <span>{t("shortcuts.title")}</span>
        <Tag className="font-normal">{t("shortcuts.badge")}</Tag>
      </summary>
      <div className="flex flex-col gap-3 px-4 pb-4">
        <p className="m-0 text-sm">{t("shortcuts.intro")}</p>
        {keys.map((k) => (
          <div key={k} className="flex flex-col gap-1">
            <Button
              variant="secondary"
              fullWidth
              loading={busy === k}
              disabled={!avail[k] || busy !== null}
              onClick={() => void run(k)}
            >
              {t(`shortcuts.${k}`)}
            </Button>
            {!avail[k] && <p className="m-0 text-xs">{t("shortcuts.unavailable", { reason: t(`shortcuts.needs.${k}`) })}</p>}
          </div>
        ))}
      </div>
    </details>
  );
}
