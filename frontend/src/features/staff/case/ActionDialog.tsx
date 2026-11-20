import { useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useConfig, useDemoNow, useSlots } from "@/api/hooks";
import { Button, Field, Input, Loading, Modal, RadioGroup, Select, Textarea, useErrorText, useToast } from "@/components";
import { formatDateTime } from "@/lib/format";
import { pickText } from "@/lib/i18nField";
import { usePersonText } from "../PersonLabel";
import { useStaffAction, useStaffUsers } from "../api";
import { useLabels } from "../labels";
import type { Action, CaseDetail, ConfigOut, SlotOut } from "../types";

/** Actions that open a form here. Closure has its own dialog. */
const NOTE_RULES: Partial<Record<Action, { field: string; min: number }>> = {
  complete_urgent_review: { field: "note", min: 5 },
  reject_referral: { field: "reason", min: 5 },
  escalate: { field: "reason", min: 5 },
  reopen: { field: "reason", min: 5 },
  refer: { field: "reason", min: 5 },
};

export const FORM_ACTIONS: Action[] = [
  "notify",
  "choose_confirmation",
  "add_reading",
  "review_confirmation",
  "refer",
  "accept_referral",
  "reject_referral",
  "assign_owner",
  "book_appointment",
  "record_visit",
  "escalate",
  "complete_urgent_review",
  "reopen",
];

interface Props {
  action: Action;
  detail: CaseDetail;
  onClose: () => void;
}

type Values = Record<string, string>;

export function ActionDialog({ action, detail, onClose }: Props) {
  const { t, i18n } = useTranslation("staff");
  const toast = useToast();
  const errorText = useErrorText();
  const labels = useLabels();
  const person = usePersonText();
  const now = useDemoNow();
  const mutation = useStaffAction(String(detail.id));
  const users = useStaffUsers();
  const config = useConfig<ConfigOut>();
  const slots = useSlots<SlotOut[]>(action === "book_appointment" ? String(detail.id) : undefined);
  const patient = detail.patient;

  const defaultTemplate = detail.severity === "SEVERE" ? "result_severe" : "result_raised";
  const [v, setV] = useState<Values>({
    template_id: patient.channel === "SMS" ? `${defaultTemplate}_sms` : defaultTemplate,
    language: patient.language,
    channel: patient.channel,
    method: "HBPM",
    outcome: action === "record_visit" ? "TREATMENT_STARTED" : "CONFIRMED",
    systolic: "",
    diastolic: "",
    pulse: "",
    source: "HOME_CUFF",
    receiver: "svc:hypertension_clinic",
    reason: "",
    note: "",
    user_id: "",
    slot_id: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [suppressed, setSuppressed] = useState(false);
  const [tried, setTried] = useState(false);
  const set = (k: string) => (value: string) => setV((x) => ({ ...x, [k]: value }));
  const onInput = (k: string) => (e: { target: { value: string } }) => set(k)(e.target.value);

  const staffOptions = useMemo(
    () =>
      (users.data ?? [])
        .filter((u) => u.region === patient.region)
        .map((u) => ({ value: String(u.id), label: `${u.display_name}, ${labels.roleTitle(u.role_title)}` })),
    [users.data, patient.region, labels],
  );
  const clinicianOptions = useMemo(
    () =>
      (users.data ?? [])
        .filter((u) => u.region === patient.region && u.role === "clinician")
        .map((u) => ({ value: `usr:${u.id}`, label: `${u.display_name}, ${labels.roleTitle(u.role_title)}` })),
    [users.data, patient.region, labels],
  );

  const templates = (config.data?.templates ?? []) as Array<{ id: string }>;
  const sms = v.channel === "SMS";
  const templateOptions = templates
    .filter((x) => x.id.endsWith("_sms") === sms)
    .map((x) => ({ value: x.id, label: labels.template(x.id) }));

  function payload(): Record<string, unknown> {
    switch (action) {
      case "notify":
        return { template_id: v.template_id, language: v.language, channel: v.channel };
      case "choose_confirmation":
        return { method: v.method };
      case "add_reading":
        return {
          systolic: Number(v.systolic),
          diastolic: Number(v.diastolic),
          pulse: v.pulse ? Number(v.pulse) : null,
          taken_at: now.toISOString(),
          source: v.source,
        };
      case "review_confirmation":
        return { outcome: v.outcome, note: v.note || null };
      case "refer":
        return v.receiver.startsWith("usr:")
          ? { to_user_id: Number(v.receiver.slice(4)), reason: v.reason }
          : { to_service: v.receiver.slice(4), reason: v.reason };
      case "reject_referral":
      case "escalate":
      case "reopen":
        return { reason: v.reason };
      case "assign_owner":
        return { user_id: Number(v.user_id) };
      case "book_appointment":
        return { slot_id: Number(v.slot_id) };
      case "record_visit":
        return { outcome: v.outcome, note: v.note || null };
      case "complete_urgent_review":
        return { note: v.note };
      default:
        return {};
    }
  }

  // Text fields that need a minimum length are checked here first, with a hint in the interface language.
  const rule = NOTE_RULES[action];
  const min = rule ? (action === "reopen" ? Number(config.data?.entries.find((e) => e.key === "reopen_reason_min_chars")?.value ?? rule.min) : rule.min) : 0;
  const tooShort = !!rule && v[rule.field]!.trim().length < min;
  const hint = (field: string) => (tried && rule?.field === field && tooShort ? t("action.tooShort", { min }) : undefined);

  function submit() {
    setError(null);
    if (tooShort) {
      setTried(true);
      return;
    }
    mutation.mutate(
      { action, payload: payload() },
      {
        onSuccess: (data) => {
          if (data.feedback?.code === "MESSAGE_SUPPRESSED") {
            // 200 from the server, but nothing was sent and the case did not move. Keep the dialog open and say so.
            setSuppressed(true);
            return;
          }
          toast.show(t("action.done", { action: t(`action.${action}.title`) }));
          onClose();
        },
        onError: (e) => setError(errorText(e)),
      },
    );
  }

  let body: ReactNode = null;
  switch (action) {
    case "notify":
      body = (
        <div className="flex flex-col gap-3">
          <Field label={t("action.fields.channel")}>
            <Select
              value={v.channel}
              onChange={onInput("channel")}
              options={["APP", "SMS", "WHATSAPP"].map((c) => ({ value: c, label: t(`channel.${c}`) }))}
            />
          </Field>
          <Field label={t("action.fields.template")}>
            <Select value={v.template_id} onChange={onInput("template_id")} options={templateOptions} />
          </Field>
          <Field label={t("action.fields.language")}>
            <Select
              value={v.language}
              onChange={onInput("language")}
              options={["en", "ar", "fr"].map((l) => ({ value: l, label: t(`language.${l}`) }))}
            />
          </Field>
        </div>
      );
      break;
    case "choose_confirmation":
      body = (
        <RadioGroup
          name="method"
          legend={t("action.fields.method")}
          value={v.method}
          onChange={set("method")}
          options={[
            { value: "HBPM", label: t("method.HBPM"), description: t("method.HBPMHint") },
            { value: "ABPM", label: t("method.ABPM"), description: t("method.ABPMHint") },
          ]}
        />
      );
      break;
    case "add_reading":
      body = (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t("action.add_reading.rule")}</p>
          <div className="grid grid-cols-3 gap-3">
            <Field label={t("action.fields.systolic")}>
              <Input inputMode="numeric" value={v.systolic} onChange={onInput("systolic")} />
            </Field>
            <Field label={t("action.fields.diastolic")}>
              <Input inputMode="numeric" value={v.diastolic} onChange={onInput("diastolic")} />
            </Field>
            <Field label={t("action.fields.pulse")} optional>
              <Input inputMode="numeric" value={v.pulse} onChange={onInput("pulse")} />
            </Field>
          </div>
          <Field label={t("action.fields.source")}>
            <Select
              value={v.source}
              onChange={onInput("source")}
              options={["HOME_CUFF", "CLINIC", "ABPM"].map((s) => ({ value: s, label: labels.source(s) }))}
            />
          </Field>
        </div>
      );
      break;
    case "review_confirmation":
      body = (
        <div className="flex flex-col gap-3">
          <RadioGroup
            name="outcome"
            legend={t("action.fields.outcome")}
            value={v.outcome}
            onChange={set("outcome")}
            options={[
              { value: "CONFIRMED", label: t("outcome.CONFIRMED"), description: t("outcome.CONFIRMEDHint") },
              { value: "NOT_CONFIRMED", label: t("outcome.NOT_CONFIRMED"), description: t("outcome.NOT_CONFIRMEDHint") },
            ]}
          />
          <Field label={t("action.fields.note")} optional>
            <Textarea value={v.note} onChange={onInput("note")} />
          </Field>
        </div>
      );
      break;
    case "refer":
      body = (
        <div className="flex flex-col gap-3">
          <Field label={t("action.fields.receiver")}>
            <Select
              value={v.receiver}
              onChange={onInput("receiver")}
              options={[{ value: "svc:hypertension_clinic", label: t("action.refer.service") }, ...clinicianOptions]}
            />
          </Field>
          <Field label={t("action.fields.reason")} error={hint("reason")}>
            <Textarea value={v.reason} onChange={onInput("reason")} />
          </Field>
        </div>
      );
      break;
    case "accept_referral":
      body = <p>{t("action.accept_referral.body")}</p>;
      break;
    case "reject_referral":
    case "escalate":
    case "reopen":
      body = (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t(`action.${action}.rule`)}</p>
          <Field label={t("action.fields.reason")} error={hint("reason")}>
            <Textarea value={v.reason} onChange={onInput("reason")} />
          </Field>
        </div>
      );
      break;
    case "assign_owner":
      body = (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t("action.assign_owner.rule")}</p>
          {users.isLoading ? (
            <Loading />
          ) : (
            <Field label={t("action.fields.newOwner")}>
              <Select value={v.user_id} onChange={onInput("user_id")} options={staffOptions} placeholder={t("action.choose")} />
            </Field>
          )}
        </div>
      );
      break;
    case "book_appointment":
      body = slots.isLoading ? (
        <Loading />
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t("action.book_appointment.rule")}</p>
          {(slots.data ?? []).length === 0 && <p>{t("action.book_appointment.none")}</p>}
          <RadioGroup
            name="slot"
            legend={t("action.fields.slot")}
            value={v.slot_id}
            onChange={set("slot_id")}
            options={(slots.data ?? []).map((s) => ({
              value: String(s.id),
              label: `${formatDateTime(s.starts_at, i18n.language)}, ${person(s.provider_person)}`,
              description: `${pickText(s.location_i18n, s.location)}. ${pickText(s.cover.label_i18n, s.cover.label)} (${t("simulatedShort")})`,
            }))}
          />
        </div>
      );
      break;
    case "record_visit":
      body = (
        <div className="flex flex-col gap-3">
          <RadioGroup
            name="visit"
            legend={t("action.fields.outcome")}
            value={v.outcome}
            onChange={set("outcome")}
            options={[
              { value: "TREATMENT_STARTED", label: t("visit.TREATMENT_STARTED") },
              { value: "SURVEILLANCE", label: t("visit.SURVEILLANCE") },
            ]}
          />
          <Field label={t("action.fields.note")} optional>
            <Textarea value={v.note} onChange={onInput("note")} />
          </Field>
        </div>
      );
      break;
    case "complete_urgent_review":
      body = (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t("action.complete_urgent_review.rule")}</p>
          <Field label={t("action.fields.reviewNote")} error={hint("note")}>
            <Textarea value={v.note} onChange={onInput("note")} />
          </Field>
        </div>
      );
      break;
    default:
      body = null;
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t(`action.${action}.title`)}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {suppressed ? t("action.dismiss") : t("action.cancel")}
          </Button>
          {!suppressed && (
            <Button loading={mutation.isPending} onClick={submit}>
              {t(`action.${action}.submit`)}
            </Button>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-3">
        {suppressed && (
          <div role="alert" className="rounded-lg border border-due bg-due-soft px-3 py-2 text-sm text-due-ink">
            <p className="font-semibold">{t("action.suppressedTitle")}</p>
            <p>{t("action.suppressedBody")}</p>
          </div>
        )}
        {!suppressed && body}
        {error && (
          <p role="alert" className="rounded-lg bg-due-soft px-3 py-2 text-sm font-medium text-due-ink">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}
