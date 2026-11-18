import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button, Card, Loading, RadioGroup, useErrorText, useToast } from "@/components";
import type { components } from "@/api/schema";
import { latestMessage, parseTeachBack, useRegionConfig, useThread, usePatientAction, type Feedback } from "./api";
import { Notice, PageTitle, useCurrentCase } from "./ui";

type RedFlag = components["schemas"]["RedFlag"];
const FLAGS: RedFlag[] = ["chest_pain", "shortness_of_breath", "severe_headache", "vision_change", "confusion", "one_sided_weakness"];
const linkBtn =
  "inline-flex min-h-11 items-center justify-center rounded-lg bg-accent px-4 py-2 font-semibold text-white hover:bg-accent-strong";

export default function Understand() {
  const { t, i18n } = useTranslation("patient");
  const toast = useToast();
  const errorText = useErrorText();
  const c = useCurrentCase();
  const thread = useThread(i18n.language);
  const region = useRegionConfig(c.region);
  const act = usePatientAction(c.id);

  const [flags, setFlags] = useState<Record<string, boolean>>({});
  const [answer, setAnswer] = useState("");
  const [confidence, setConfidence] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [passed, setPassed] = useState(false);
  const [recorded, setRecorded] = useState(false);

  const anyFlag = FLAGS.some((f) => flags[f]);
  const emergencyText =
    region.region?.emergency_text[i18n.language] ?? region.region?.emergency_text.en ?? t("understand.emergencyFallback");

  if (c.state === "RESULT_ISSUED") {
    return (
      <div className="flex flex-col gap-4">
        <PageTitle>{t("understand.heading")}</PageTitle>
        <Notice>{t("understand.notYet")}</Notice>
      </div>
    );
  }

  if (c.state !== "NOTIFIED" && !passed) {
    return (
      <div className="flex flex-col gap-4">
        <PageTitle>{t("understand.heading")}</PageTitle>
        <Notice tone="accent">{t("understand.alreadyDone")}</Notice>
        <Link to="/patient" className={linkBtn}>
          {t("nav.home")}
        </Link>
      </div>
    );
  }

  if (passed) {
    return (
      <div className="flex flex-col gap-4">
        <PageTitle>{t("understand.heading")}</PageTitle>
        <Notice tone="accent" title={t("understand.doneTitle")}>
          {t("understand.doneText")}
        </Notice>
        {recorded && <Notice tone="due">{t("understand.emergencyRecorded")}</Notice>}
        <Link to="/patient/confirm" className={linkBtn}>
          {t("understand.toConfirm")}
        </Link>
      </div>
    );
  }

  const question = latestMessage(thread.data, "teach_back_question");
  const tb = question ? parseTeachBack(question.text) : null;
  const simpler = latestMessage(thread.data, "teach_back_simpler");

  const submit = () => {
    setSubmitted(true);
    if (!answer || !confidence) return;
    const red = FLAGS.filter((f) => flags[f]);
    act.mutate(
      {
        action: "acknowledge",
        payload: { teach_back_answer: answer, red_flags: red, confidence: Number(confidence) },
      },
      {
        onSuccess: (detail) => {
          const fb = (detail.feedback ?? null) as Feedback | null;
          if (red.length) setRecorded(true);
          if (detail.state === "ACKNOWLEDGED") {
            setPassed(true);
            setFeedback(null);
          } else {
            setFeedback(fb);
            setAnswer("");
            setSubmitted(false);
          }
        },
        onError: (e) => toast.show(errorText(e), "due"),
      },
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>{t("understand.heading")}</PageTitle>
      <p className="text-muted">{t("understand.intro")}</p>

      <Card title={t("understand.flagsTitle")}>
        <div className="flex flex-col gap-3">
          <p>{t("understand.flagsIntro")}</p>
          {anyFlag && (
            <Notice tone="due" title={t("understand.emergencyTitle")}>
              <p className="m-0 text-lg font-semibold">{emergencyText}</p>
              <p className="m-0 mt-2 text-base">{t("understand.emergencyAfter")}</p>
            </Notice>
          )}
          {FLAGS.map((f) => (
            <RadioGroup
              key={f}
              name={`flag-${f}`}
              legend={t(`understand.flags.${f}`)}
              inline
              value={flags[f] ? "yes" : "no"}
              onChange={(v) => setFlags((s) => ({ ...s, [f]: v === "yes" }))}
              options={[
                { value: "no", label: t("understand.no") },
                { value: "yes", label: t("understand.yes") },
              ]}
            />
          ))}
        </div>
      </Card>

      <Card title={t("understand.tbTitle")}>
        {thread.isLoading ? (
          <Loading />
        ) : !tb || tb.options.length === 0 ? (
          <p className="text-muted">{t("understand.tbMissing")}</p>
        ) : (
          <div className="flex flex-col gap-4">
            <p className="font-medium">{tb.question}</p>
            {feedback && feedback.code === "TEACH_BACK_RETRY" && (
              <Notice tone="accent" title={t("understand.retryTitle")}>
                <p className="m-0 whitespace-pre-line">{simpler?.text ?? feedback.message}</p>
                <p className="m-0 mt-2 text-sm">{t("understand.retryHint")}</p>
              </Notice>
            )}
            <RadioGroup
              name="teach-back"
              legend={t("understand.tbLegend")}
              value={answer}
              onChange={setAnswer}
              error={submitted && !answer ? t("understand.needAnswer") : undefined}
              options={tb.options.map((o) => ({ value: o.id, label: o.label }))}
            />
            <RadioGroup
              name="confidence"
              legend={t("understand.confidenceLegend")}
              inline
              value={confidence}
              onChange={setConfidence}
              error={submitted && !confidence ? t("understand.needConfidence") : undefined}
              options={["1", "2", "3", "4", "5"].map((n) => ({ value: n, label: <bdi>{n}</bdi> }))}
            />
            <p className="-mt-2 flex justify-between text-sm text-muted">
              <span>1 {t("understand.confidenceLow")}</span>
              <span>5 {t("understand.confidenceHigh")}</span>
            </p>
            <Button size="lg" fullWidth loading={act.isPending} onClick={submit}>
              {t("understand.submit")}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
