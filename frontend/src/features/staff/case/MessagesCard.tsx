import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useConfig } from "@/api/hooks";
import { Badge, Button, Card, EmptyState, Field, Select, SimulatedTag, useErrorText, useToast } from "@/components";
import { formatDateTime } from "@/lib/format";
import { useDraft, useSendDraft } from "../api";
import { useLabels } from "../labels";
import type { CaseDetail, Channel, ConfigOut, DraftOut, Language } from "../types";

const TONES = ["warmer", "simpler", "shorter"] as const;

/** The draft panel: template text first, optional AI re-wording that staff must approve before it can be sent. */
function DraftPanel({ detail }: { detail: CaseDetail }) {
  const { t } = useTranslation("staff");
  const toast = useToast();
  const errorText = useErrorText();
  const labels = useLabels();
  const config = useConfig<ConfigOut>();
  const draftM = useDraft(String(detail.id));
  const sendM = useSendDraft(String(detail.id));
  const patient = detail.patient;
  const sms = patient.channel === "SMS";

  const [templateId, setTemplateId] = useState("");
  const [language, setLanguage] = useState<Language>(patient.language);
  const [channel, setChannel] = useState<Channel>(patient.channel);
  const [tone, setTone] = useState("");
  const [draft, setDraft] = useState<DraftOut | null>(null);
  const [approved, setApproved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const templates = ((config.data?.templates ?? []) as Array<{ id: string }>).filter((x) => x.id.endsWith("_sms") === (channel === "SMS"));
  const reworded = draft?.source === "AI_REWORDED";
  const validation = (draft?.validation ?? {}) as { passed?: boolean; failed_reason?: string | null; provider?: string };
  const providerOff = !!draft && !!tone && !reworded && validation.provider === "none";
  const rejected = !!draft && !!tone && !reworded && validation.passed === false;

  function preview() {
    setError(null);
    setApproved(false);
    draftM.mutate(
      { template_id: templateId, language, tone: tone || null },
      { onSuccess: setDraft, onError: (e) => setError(errorText(e)) },
    );
  }

  function send() {
    if (!draft) return;
    setError(null);
    sendM.mutate(
      { draft, channel, approve: reworded ? approved : false },
      {
        onSuccess: () => {
          toast.show(t("messages.sent"));
          setDraft(null);
          setApproved(false);
        },
        onError: (e) => setError(errorText(e)),
      },
    );
  }

  return (
    <section className="mt-4 rounded-lg border border-line bg-surface-2 p-3" aria-labelledby="draft-heading">
      <h3 id="draft-heading" className="text-sm font-semibold">{t("messages.draftTitle")}</h3>
      <p className="mt-1 text-sm text-muted">{t("messages.draftIntro")}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Field label={t("action.fields.template")}>
          <Select
            value={templateId}
            onChange={(e) => {
              setTemplateId(e.target.value);
              setDraft(null);
            }}
            placeholder={t("action.choose")}
            options={templates.map((x) => ({ value: x.id, label: labels.template(x.id) }))}
          />
        </Field>
        <Field label={t("action.fields.language")}>
          <Select
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value as Language);
              setDraft(null);
            }}
            options={["en", "ar", "fr"].map((l) => ({ value: l, label: t(`language.${l}`) }))}
          />
        </Field>
        <Field label={t("action.fields.channel")}>
          <Select
            value={channel}
            onChange={(e) => {
              setChannel(e.target.value as Channel);
              setTemplateId("");
              setDraft(null);
            }}
            options={(sms ? ["SMS", "APP", "WHATSAPP"] : ["APP", "WHATSAPP", "SMS"]).map((c) => ({ value: c, label: t(`channel.${c}`) }))}
          />
        </Field>
        <Field label={t("messages.toneLabel")} hint={t("messages.toneHint")} optional>
          <Select
            value={tone}
            onChange={(e) => {
              setTone(e.target.value);
              setDraft(null);
            }}
            placeholder={t("messages.noRewording")}
            options={TONES.map((x) => ({ value: x, label: t(`messages.tone.${x}`) }))}
          />
        </Field>
      </div>
      <div className="mt-3">
        <Button variant="secondary" disabled={!templateId} loading={draftM.isPending} onClick={preview}>
          {t("messages.preview")}
        </Button>
      </div>

      {draft && (
        <div className="mt-3 flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={reworded ? "info" : "accent"}>{reworded ? t("messages.sourceAi") : t("messages.sourceTemplate")}</Badge>
            <span className="text-xs text-muted">
              {t("messages.templateVersion", { id: labels.template(draft.template_id), version: draft.template_version })}
            </span>
          </div>
          <p
            lang={draft.language}
            dir={draft.language === "ar" ? "rtl" : "ltr"}
            className="whitespace-pre-wrap rounded-lg border border-line bg-surface p-3 text-sm"
          >
            {draft.text}
          </p>
          {providerOff && <p className="rounded-lg bg-info-soft px-3 py-2 text-sm text-info-ink">{t("messages.providerOff")}</p>}
          {rejected && (
            <p className="rounded-lg bg-due-soft px-3 py-2 text-sm text-due-ink">
              {t("messages.rewordRejected", { reason: validation.failed_reason ?? "" })}
            </p>
          )}
          {reworded && (
            <div className="rounded-lg border border-line bg-surface p-3 text-sm">
              <p className="font-medium">{t("messages.aiNotice")}</p>
              <p className="text-muted">
                {validation.passed ? t("messages.validationPassed", { provider: validation.provider ?? "" }) : t("messages.validationFailed")}
              </p>
              <label className="mt-2 flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={approved}
                  onChange={(e) => setApproved(e.target.checked)}
                  className="mt-1 size-4 accent-[var(--color-accent)]"
                />
                <span>{t("messages.approveLabel")}</span>
              </label>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={reworded && !approved} loading={sendM.isPending} onClick={send}>
              {t("messages.send", { channel: t(`channel.${channel}`) })}
            </Button>
            {reworded && !approved && <span className="text-sm text-muted">{t("messages.needsApproval")}</span>}
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 rounded-lg bg-due-soft px-3 py-2 text-sm font-medium text-due-ink">
          {error}
        </p>
      )}
      <p className="mt-3 text-xs text-muted">{t("messages.aiBoundary")}</p>
    </section>
  );
}

export function MessagesCard({ detail }: { detail: CaseDetail }) {
  const { t, i18n } = useTranslation("staff");
  const labels = useLabels();
  const msgs = [...detail.messages].sort((a, b) => a.created_at.localeCompare(b.created_at));
  return (
    <Card title={t("messages.title")} action={<SimulatedTag />}>
      {msgs.length === 0 ? (
        <EmptyState description={t("messages.empty")} />
      ) : (
        <ul className="flex max-h-96 flex-col gap-3 overflow-y-auto">
          {msgs.map((m) => (
            <li key={m.id} className={`rounded-lg border border-line p-3 text-sm ${m.direction === "IN" ? "bg-surface-2" : "bg-surface"}`}>
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                <Badge tone={m.direction === "IN" ? "neutral" : "info"}>{m.direction === "IN" ? t("messages.fromPatient") : t("messages.toPatient")}</Badge>
                <span>{t(`channel.${m.channel}`)}</span>
                <span>{t(`language.${m.language}`)}</span>
                <span>{formatDateTime(m.created_at, i18n.language)}</span>
                {m.source === "AI_REWORDED" && <Badge tone="info">{t("messages.sourceAi")}</Badge>}
                {m.template_id && <span>{labels.template(m.template_id)}</span>}
              </div>
              <p lang={m.language} dir={m.language === "ar" ? "rtl" : "ltr"} className="whitespace-pre-wrap">
                {m.text}
              </p>
              {(m.sender_name || m.approved_by_name) && (
                <p className="mt-1 text-xs text-muted">
                  {m.sender_name && t("messages.sentBy", { name: m.sender_name })}
                  {m.approved_by_name && ` ${t("messages.approvedBy", { name: m.approved_by_name })}`}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      {detail.state !== "CLOSED" && <DraftPanel detail={detail} />}
    </Card>
  );
}
