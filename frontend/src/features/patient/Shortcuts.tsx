import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { Button, useErrorText, useToast } from "@/components";
import { actAs, advanceClockAs, fromZonedInput, replyAs, slotsAs, toZonedInput, useDiary, useRegionZone, type PatientCase } from "./api";
import { useDemoClock } from "@/api/hooks";

type Flow = "auh" | "yde";
type Key = "abpm" | "review" | "referral" | "book" | "visit" | "skip" | "close" | "sampleWeek";

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
  const tz = useRegionZone(c.region);
  const clock = useDemoClock();
  const [busy, setBusy] = useState<Key | null>(null);
  const who = STAFF[flow];
  const who_ = { abpm: "coordinator_auh" } as const;

  const state = c.state;
  const avail: Record<Key, boolean> = {
    abpm: state === "ACKNOWLEDGED" && c.confirmation?.method === "ABPM" && c.confirmation?.status !== "CONFIRMED_RAISED",
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
      if (key === "abpm") {
        // The clinic enters the 24 hour monitor series from the diary endpoint, dated two days back on the region's clock.
        const day = toZonedInput(new Date(new Date(clock.data?.now ?? Date.now()).getTime() - 2 * 86_400_000), tz).slice(0, 10);
        let who = "";
        for (const r of diary.data?.abpm_sample ?? []) {
          const base = new Date(`${day}T00:00:00Z`);
          if (r.time < "07:00") base.setUTCDate(base.getUTCDate() + 1);
          const local = `${base.toISOString().slice(0, 10)}T${r.time}`;
          const done = await actAs(who_.abpm, c.id, "add_reading", {
            systolic: r.systolic, diastolic: r.diastolic, pulse: r.pulse ?? null, taken_at: fromZonedInput(local, tz), source: "ABPM",
          });
          who = done.who;
        }
        toast.show(t("shortcuts.did.abpm", { who }));
      } else if (key === "review") {
        const r = await actAs(who.review, c.id, "review_confirmation", {
          outcome: "CONFIRMED",
          note: t("shortcuts.note.review", { lng: "en" }),
        });
        toast.show(t("shortcuts.did.review", { who: r.who }));
      } else if (key === "referral") {
        if (state === "CONFIRMED") {
          const r = await actAs(who.refer, c.id, "refer", {
            to_service: "hypertension_clinic",
            reason: t("shortcuts.note.refer", { lng: "en" }),
          });
          toast.show(t("shortcuts.did.refer", { who: r.who }));
        }
        const a = await actAs(who.accept, c.id, "accept_referral", {});
        toast.show(t("shortcuts.did.accept", { who: a.who }));
      } else if (key === "book") {
        const slots = await slotsAs(who.book, c.id);
        const first = slots[0];
        if (!first) throw { status: 404, code: "NO_SLOTS", message: t("visit.slotsEmpty") };
        const r = await actAs(who.book, c.id, "book_appointment", { slot_id: first.id });
        toast.show(t("shortcuts.did.book", { who: r.who }));
      } else if (key === "visit") {
        const r = await actAs(who.visit, c.id, "record_visit", { outcome: "TREATMENT_STARTED" });
        toast.show(t("shortcuts.did.visit", { who: r.who }));
      } else if (key === "close") {
        const r = await actAs(who.close, c.id, "close", {
          evidence_type: "OTHER_CLINICAL_DECISION",
          decision_note: t("shortcuts.note.close", { lng: "en" }),
        });
        toast.show(t("shortcuts.did.close", { who: r.who }));
      } else if (key === "skip") {
        await advanceClockAs(who.clock, SKIP_HOURS);
        toast.show(t("shortcuts.did.skip"));
      } else if (key === "sampleWeek") {
        // Reads the sample series from the diary endpoint and sends each reading as a text message,
        // moving the demo clock 12 hours between messages so the readings land on different days.
        const sample = (diary.data?.hbpm_sample ?? []).filter((r) => r.systolic < 180 && r.diastolic < 110); // a severe value would send the urgent message
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

  const keys: Key[] = flow === "auh" ? ["abpm", "review", "referral", "visit", "skip", "close"] : ["sampleWeek", "review", "referral", "book", "visit", "skip", "close"];

  return (
    <details className="demo-outline rounded-card text-sm text-ink">
      <summary className="flex min-h-11 cursor-pointer items-center justify-between gap-2 px-4 py-2">
        <span className="font-medium">{t("shortcuts.title")}</span>
        <span className="text-xs text-muted">{t("shortcuts.badge")}</span>
      </summary>
      <div className="flex flex-col gap-2.5 px-4 pb-4">
        <p className="m-0 text-xs text-muted">{t("shortcuts.intro")}</p>
        {keys.map((k) => (
          <div key={k} className="flex flex-col gap-0.5">
            <Button variant="secondary" size="sm" fullWidth loading={busy === k} disabled={!avail[k] || busy !== null} onClick={() => void run(k)} className="min-h-11 justify-start text-start">
              {t(`shortcuts.${k}`)}
            </Button>
            {(k === "skip" || k === "sampleWeek") && avail[k] && <p className="m-0 ps-1 text-xs text-muted">{t("shortcuts.clockNote")}</p>}
            {!avail[k] && <p className="m-0 ps-1 text-xs text-muted">{t("shortcuts.unavailable", { reason: t(`shortcuts.needs.${k}`) })}</p>}
          </div>
        ))}
      </div>
    </details>
  );
}
