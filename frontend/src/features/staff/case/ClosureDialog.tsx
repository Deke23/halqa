import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useConfig } from "@/api/hooks";
import { Button, Field, Input, Modal, Select, Textarea, useErrorText, useToast } from "@/components";
import { formatDateTime } from "@/lib/format";
import { useStaffAction } from "../api";
import { useLabels } from "../labels";
import type { CaseDetail, ConfigOut } from "../types";

interface Props {
  detail: CaseDetail;
  onClose: () => void;
}

/**
 * Closure dialog. The rule is written out in words. The button is never disabled for an incomplete form:
 * the submit goes to the server, and the server's refusal is shown here.
 */
export function ClosureDialog({ detail, onClose }: Props) {
  const { t, i18n } = useTranslation("staff");
  const toast = useToast();
  const errorText = useErrorText();
  const labels = useLabels();
  const config = useConfig<ConfigOut>();
  const mutation = useStaffAction(String(detail.id));
  const [type, setType] = useState<string>(detail.suggested_closure_type ?? "");
  const [readingRef, setReadingRef] = useState("");
  const [docLabel, setDocLabel] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const types = config.data?.closure_evidence_types ?? [];
  const minNote = Number(config.data?.entries.find((e) => e.section === "closure" && e.key === "note_min_chars")?.value ?? 10);
  const ref = readingRef || docLabel.trim();

  function submit() {
    setError(null);
    mutation.mutate(
      {
        action: "close",
        payload: { evidence_type: type || null, evidence_ref: ref || null, decision_note: note.trim() || null },
      },
      {
        onSuccess: () => {
          toast.show(t("closure.done"));
          onClose();
        },
        onError: (e) => setError(errorText(e)),
      },
    );
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t("closure.title")}
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("action.cancel")}
          </Button>
          <Button loading={mutation.isPending} onClick={submit}>
            {t("closure.submit")}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {error && (
          <p role="alert" className="rounded-lg bg-due-soft px-3 py-2 text-sm font-medium text-due-ink">
            {t("closure.refused")} {error}
          </p>
        )}
        <div className="rounded-lg bg-info-soft px-3 py-2 text-sm text-info-ink">
          <p className="font-semibold">{t("closure.ruleTitle")}</p>
          <p>{t("closure.rule", { min: minNote })}</p>
        </div>
        {detail.suggested_closure_type && (
          <p className="text-sm text-muted">{t("closure.suggested", { type: labels.evidence(detail.suggested_closure_type) })}</p>
        )}
        <Field label={t("closure.evidenceType")}>
          <Select
            value={type}
            onChange={(e) => setType(e.target.value)}
            options={types.map((x) => ({ value: x, label: labels.evidence(x) }))}
            placeholder={t("action.choose")}
          />
        </Field>
        <fieldset className="flex flex-col gap-3 rounded-lg border border-line p-3">
          <legend className="px-1 text-sm font-medium">{t("closure.refLegend")}</legend>
          <Field label={t("closure.pickReading")} optional>
            <Select
              value={readingRef}
              onChange={(e) => setReadingRef(e.target.value)}
              placeholder={t("closure.noReading")}
              options={detail.readings.map((r) => ({
                value: `reading:${r.id}`,
                label: `${r.systolic}/${r.diastolic}, ${formatDateTime(r.taken_at, i18n.language)}, ${labels.source(r.source)}`,
              }))}
            />
          </Field>
          <Field label={t("closure.docLabel")} hint={t("closure.docHint")} optional>
            <Input value={docLabel} onChange={(e) => setDocLabel(e.target.value)} />
          </Field>
        </fieldset>
        <Field label={t("closure.note")} hint={t("closure.noteHint", { min: minNote, count: note.trim().length })} optional>
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}
