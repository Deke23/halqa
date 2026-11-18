import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { Badge, Button, Card, EmptyState, Field, Select, Textarea, useErrorText, useToast } from "@/components";
import { formatDateTime } from "@/lib/format";
import { useAnswerEconsult, useAskEconsult, useMyUserId, useStaffUsers } from "../api";
import type { CaseDetail, EConsult } from "../types";

function ReplyForm({ e }: { e: EConsult }) {
  const { t } = useTranslation("staff");
  const toast = useToast();
  const errorText = useErrorText();
  const reply = useAnswerEconsult();
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="mt-2 flex flex-col gap-2">
      <Field label={t("econsult.yourAnswer")}>
        <Textarea value={answer} onChange={(x) => setAnswer(x.target.value)} />
      </Field>
      {error && (
        <p role="alert" className="text-sm font-medium text-due-ink">
          {error}
        </p>
      )}
      <div>
        <Button
          size="sm"
          loading={reply.isPending}
          onClick={() => {
            setError(null);
            reply.mutate(
              { econsultId: e.id, answer },
              { onSuccess: () => toast.show(t("econsult.answered")), onError: (x) => setError(errorText(x)) },
            );
          }}
        >
          {t("econsult.sendAnswer")}
        </Button>
      </div>
    </div>
  );
}

function AskForm({ detail }: { detail: CaseDetail }) {
  const { t } = useTranslation("staff");
  const toast = useToast();
  const errorText = useErrorText();
  const users = useStaffUsers();
  const myId = useMyUserId();
  const ask = useAskEconsult(String(detail.id));
  const [to, setTo] = useState("");
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const options = (users.data ?? [])
    .filter((u) => u.role === "clinician" && u.id !== myId && u.region === detail.patient.region)
    .map((u) => ({ value: String(u.id), label: u.name }));
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-sm font-medium text-accent-ink">{t("econsult.askTitle")}</summary>
      <div className="mt-2 flex flex-col gap-3">
        <Field label={t("econsult.askTo")}>
          <Select value={to} onChange={(e) => setTo(e.target.value)} options={options} placeholder={t("action.choose")} />
        </Field>
        <Field label={t("econsult.question")}>
          <Textarea value={question} onChange={(e) => setQuestion(e.target.value)} />
        </Field>
        {error && (
          <p role="alert" className="text-sm font-medium text-due-ink">
            {error}
          </p>
        )}
        <div>
          <Button
            variant="secondary"
            loading={ask.isPending}
            onClick={() => {
              setError(null);
              ask.mutate(
                { to_user_id: Number(to), question },
                {
                  onSuccess: () => {
                    toast.show(t("econsult.asked"));
                    setQuestion("");
                  },
                  onError: (x) => setError(errorText(x)),
                },
              );
            }}
          >
            {t("econsult.ask")}
          </Button>
        </div>
      </div>
    </details>
  );
}

export function EconsultCard({ detail }: { detail: CaseDetail }) {
  const { t, i18n } = useTranslation("staff");
  const { user } = useAuth();
  const myId = useMyUserId();
  const items = [...detail.econsults].sort((a, b) => a.created_at.localeCompare(b.created_at));
  return (
    <Card title={t("econsult.title")}>
      {items.length === 0 ? (
        <EmptyState description={t("econsult.empty")} />
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((e) => (
            <li key={e.id} className="rounded-lg border border-line p-3 text-sm">
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                <Badge tone={e.status === "OPEN" ? "due" : "accent"}>{t(`econsult.status.${e.status}`)}</Badge>
                <span>{t("econsult.route", { from: e.from_name, to: e.to_name })}</span>
                <span>{formatDateTime(e.created_at, i18n.language)}</span>
              </div>
              <p>
                <span className="font-medium">{t("econsult.questionLabel")}</span> {e.question}
              </p>
              {e.answer && (
                <p className="mt-1">
                  <span className="font-medium">{t("econsult.answerLabel")}</span> {e.answer}
                </p>
              )}
              {e.status === "OPEN" && myId === e.to_user_id && <ReplyForm e={e} />}
              {e.status === "OPEN" && myId !== e.to_user_id && <p className="mt-1 text-muted">{t("econsult.waiting", { name: e.to_name })}</p>}
            </li>
          ))}
        </ul>
      )}
      {user?.role === "clinician" && detail.state !== "CLOSED" && <AskForm detail={detail} />}
    </Card>
  );
}
