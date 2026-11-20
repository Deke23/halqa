import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button, useErrorText, useToast } from "@/components";
import type { components } from "@/api/schema";
import { cx } from "@/lib/cx";
import { useRegionConfig, usePatientAction, type Feedback } from "./api";
import { ChoiceGroup, Notice, PageTitle, Panel, Readout, primaryLink, useCurrentCase } from "./ui";

type RedFlag = components["schemas"]["RedFlag"];
const FLAGS: RedFlag[] = ["chest_pain", "shortness_of_breath", "severe_headache", "vision_change", "confusion", "one_sided_weakness"];
const QUESTION_STEP = FLAGS.length; // 0..5 warning signs, 6 teach-back, 7 confidence
const TOTAL = FLAGS.length + 2;

/** One question at a time. Warning signs first, then the teach-back question, then a confidence rating. */
export default function Understand() {
  const { t, i18n } = useTranslation("patient");
  const toast = useToast();
  const errorText = useErrorText();
  const c = useCurrentCase();
  const region = useRegionConfig(c.region);
  const act = usePatientAction(c.id);

  const [step, setStep] = useState(0);
  const [flags, setFlags] = useState<Record<string, boolean>>({});
  const [answer, setAnswer] = useState("");
  const [confidence, setConfidence] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [passed, setPassed] = useState(false);
  const [recorded, setRecorded] = useState(false);

  const anyFlag = FLAGS.some((f) => flags[f]);
  const emergencyText = region.region?.emergency_text[i18n.language] ?? region.region?.emergency_text.en ?? t("understand.emergencyFallback");

  if (c.state === "RESULT_ISSUED") {
    return (
      <div className="flex flex-col gap-5">
        <PageTitle>{t("understand.heading")}</PageTitle>
        <Notice>{t("understand.notYet")}</Notice>
      </div>
    );
  }

  if (passed || c.state !== "NOTIFIED") {
    return (
      <div className="flex flex-col gap-5">
        <PageTitle>{t("understand.heading")}</PageTitle>
        <Notice tone="accent" title={passed ? t("understand.doneTitle") : undefined}>
          {passed ? t("understand.doneText") : t("understand.alreadyDone")}
        </Notice>
        {passed && recorded && <Notice tone="due">{t("understand.emergencyRecorded")}</Notice>}
        <Link to={passed ? "/patient/confirm" : "/patient"} className={primaryLink}>
          {passed ? t("understand.toConfirm") : t("nav.home")}
        </Link>
      </div>
    );
  }

  const tb = c.teach_back ?? null;

  const submit = () => {
    const red = FLAGS.filter((f) => flags[f]);
    act.mutate(
      { action: "acknowledge", payload: { teach_back_answer: answer, red_flags: red, confidence: Number(confidence) } },
      {
        onSuccess: (detail) => {
          if (red.length) setRecorded(true);
          if (detail.state === "ACKNOWLEDGED") {
            setPassed(true);
            setFeedback(null);
          } else {
            setFeedback((detail.feedback ?? null) as Feedback | null);
            setAnswer("");
            setStep(QUESTION_STEP);
          }
        },
        onError: (e) => toast.show(errorText(e), "due"),
      },
    );
  };

  const answerFlag = (f: RedFlag, yes: boolean) => {
    setFlags((s) => ({ ...s, [f]: yes }));
    setStep((n) => n + 1);
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <PageTitle>{t("understand.heading")}</PageTitle>
        <p className="m-0 text-sm text-muted">{t("understand.progress", { n: step + 1, total: TOTAL })}</p>
        <div aria-hidden="true" className="mt-1 flex gap-1">
          {Array.from({ length: TOTAL }, (_, i) => (
            <span key={i} className={cx("h-1 flex-1 rounded-full", i <= step ? "bg-accent" : "bg-line")} />
          ))}
        </div>
      </div>

      {anyFlag && (
        <Notice tone="due" title={t("understand.emergencyTitle")}>
          <p className="m-0 text-lg font-semibold">{emergencyText}</p>
          <p className="m-0 mt-2 text-base">{t("understand.emergencyAfter")}</p>
        </Notice>
      )}

      {step < QUESTION_STEP && (
        <Panel key={step}>
          <fieldset className="m-0 flex min-w-0 flex-col gap-5 border-0 p-0">
            <legend className="mb-5 p-0 text-xl font-semibold leading-snug">
              {t("understand.flagsIntro")}
              <span className="mt-1 block text-lg">{t(`understand.flags.${FLAGS[step]!}`)}</span>
            </legend>
            <div className="grid grid-cols-2 gap-3">
              <Button variant="secondary" size="lg" aria-label={`${t(`understand.flags.${FLAGS[step]!}`)}: ${t("understand.no")}`} onClick={() => answerFlag(FLAGS[step]!, false)}>
                {t("understand.no")}
              </Button>
              <Button variant="secondary" size="lg" aria-label={`${t(`understand.flags.${FLAGS[step]!}`)}: ${t("understand.yes")}`} onClick={() => answerFlag(FLAGS[step]!, true)}>
                {t("understand.yes")}
              </Button>
            </div>
          </fieldset>
        </Panel>
      )}

      {step === QUESTION_STEP && (
        <Panel>
          {!tb || tb.options.length === 0 ? (
            <p className="m-0 text-muted">{t("understand.tbMissing")}</p>
          ) : (
            <div className="flex flex-col gap-4">
              <p className="m-0 text-xl font-semibold leading-snug">
                <bdi>{tb.question}</bdi>
              </p>
              {feedback && feedback.code === "TEACH_BACK_RETRY" && (
                <Notice tone="accent" title={t("understand.retryTitle")}>
                  <p className="m-0 whitespace-pre-line">{tb.simpler || feedback.message}</p>
                  <p className="m-0 mt-2 text-sm">{t("understand.retryHint")}</p>
                </Notice>
              )}
              <ChoiceGroup
                name="teach-back"
                legend={t("understand.tbLegend")}
                value={answer}
                onChange={setAnswer}
                options={tb.options.map((label, i) => ({ value: String(i + 1), label, text: label }))}
              />
              <Button size="lg" fullWidth disabled={!answer} onClick={() => setStep(QUESTION_STEP + 1)}>
                {t("generic.next", { ns: "common" })}
              </Button>
            </div>
          )}
        </Panel>
      )}

      {step === QUESTION_STEP + 1 && (
        <Panel>
          <div className="flex flex-col gap-4">
            <ChoiceGroup
              name="confidence"
              legend={<span className="text-xl font-semibold leading-snug">{t("understand.confidenceLegend")}</span>}
              inline
              value={confidence}
              onChange={setConfidence}
              options={["1", "2", "3", "4", "5"].map((n) => ({ value: n, label: <Readout>{n}</Readout>, text: t("understand.confidenceValue", { n }) }))}
            />
            <p className="-mt-2 flex justify-between text-sm text-muted">
              <span>
                <Readout>1</Readout> {t("understand.confidenceLow")}
              </span>
              <span>
                <Readout>5</Readout> {t("understand.confidenceHigh")}
              </span>
            </p>
            <Button size="lg" fullWidth loading={act.isPending} disabled={!confidence} onClick={submit}>
              {t("understand.submit")}
            </Button>
          </div>
        </Panel>
      )}

      {step > 0 && (
        <Button variant="ghost" onClick={() => setStep((n) => Math.max(0, n - 1))} className="self-start">
          {t("generic.back", { ns: "common" })}
        </Button>
      )}
    </div>
  );
}
