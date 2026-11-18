import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, EmptyState, ErrorState, Loading, SimulatedTag, useErrorText } from "@/components";
import { cx } from "@/lib/cx";
import { formatDate, localeFor } from "@/lib/format";
import { initials } from "@/lib/format";
import { usePatientCase, useSendReply, useThread, type MessageOut, type PatientCase } from "@/features/patient/api";
import { Shortcuts } from "@/features/patient/Shortcuts";
import { plainName } from "@/features/patient/ui";

type Look = "sms" | "whatsapp";

function shortTime(iso: string, lng: string): string {
  return new Intl.DateTimeFormat(localeFor(lng), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }).format(new Date(iso));
}

/** Yaoundé patient: an SMS or WhatsApp style thread. Replies are parsed by fixed rules on the server. */
export default function PhoneThread() {
  const { t, i18n } = useTranslation("patient");
  const caseQ = usePatientCase();
  const thread = useThread(i18n.language, true);
  const send = useSendReply();
  const errorText = useErrorText();
  const [look, setLook] = useState<Look>("sms");
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const count = thread.data?.length ?? 0;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [count]);

  if (caseQ.isLoading) return <Loading />;
  if (caseQ.error) return <ErrorState error={caseQ.error} onRetry={() => void caseQ.refetch()} />;
  const c = caseQ.data;
  if (!c) return <EmptyState title={t("noCase.title")} description={t("noCase.description")} />;

  const wa = look === "whatsapp";
  const contact = plainName(thread.data?.find((m) => m.direction === "OUT" && m.sender_name)?.sender_name ?? c.owner_name);
  const post = (value: string) => {
    const v = value.trim();
    if (!v || send.isPending) return;
    send.mutate({ text: v }, { onSuccess: () => setText("") });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Header c={c} contact={contact} look={look} onLook={setLook} />

      <div
        role="log"
        aria-live="polite"
        aria-label={t("phone.title")}
        className={cx("min-h-0 flex-1 overflow-y-auto px-3 py-3", wa ? "bg-accent-soft" : "bg-surface-2")}
      >
        {thread.isLoading ? (
          <Loading />
        ) : thread.error ? (
          <ErrorState error={thread.error} title={t("phone.loadError")} onRetry={() => void thread.refetch()} />
        ) : count === 0 ? (
          <p className="text-center text-sm text-muted">{t("phone.empty")}</p>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {thread.data!.map((m) => (
              <Bubble key={m.id} m={m} wa={wa} lng={i18n.language} />
            ))}
          </ul>
        )}
        <div ref={endRef} />
      </div>

      <div className="max-h-[40%] overflow-y-auto border-t border-line bg-surface p-2">
        <Shortcuts c={c} flow="yde" />
      </div>

      <div className="border-t border-line bg-surface p-2">
        <QuickReplies state={c.state} onPick={post} disabled={send.isPending} />
        {send.isError && (
          <p role="alert" className="m-0 mb-1 rounded bg-due-soft px-2 py-1 text-sm text-due-ink">
            {errorText(send.error)}
          </p>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            post(text);
          }}
          className="flex items-center gap-2"
        >
          <label htmlFor="phone-reply" className="sr-only">
            {t("phone.inputLabel")}
          </label>
          <input
            id="phone-reply"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t("phone.inputPlaceholder")}
            autoComplete="off"
            inputMode="text"
            className="min-h-11 min-w-0 flex-1 rounded-full border border-line bg-surface px-4 text-base placeholder:text-muted"
          />
          <Button type="submit" size="md" loading={send.isPending} disabled={!text.trim()}>
            {t("phone.send")}
          </Button>
        </form>
        <p className="m-0 mt-1 px-1 text-xs text-muted">{c.state === "IN_CARE" ? t("phone.hintCare") : t("phone.hint")}</p>
      </div>
    </div>
  );
}

function Header({ c, contact, look, onLook }: { c: PatientCase; contact: string; look: Look; onLook: (l: Look) => void }) {
  const { t, i18n } = useTranslation("patient");
  const wa = look === "whatsapp";
  const owner = plainName(c.next_step?.owner_name ?? c.owner_name);
  const due = c.next_step?.due_at;
  return (
    <div className={cx("flex flex-col gap-2 border-b border-line px-3 py-2", wa ? "bg-accent-strong text-white" : "bg-surface")}>
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className={cx("flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold", wa ? "bg-white text-accent-ink" : "bg-accent text-white")}
        >
          {initials(contact) || "?"}
        </span>
        <div className="min-w-0 flex-1">
          <p className="m-0 truncate font-semibold">
            <span className={cx("me-1 text-xs font-normal", wa ? "text-white" : "text-muted")}>{t("phone.contact")}:</span>
            <bdi>{contact}</bdi>
          </p>
          <p className={cx("m-0 text-xs leading-snug", wa ? "text-white" : "text-muted")}>
            {c.state !== "CLOSED" && due ? (
              <bdi>{t("phone.stepOwner", { name: owner, date: formatDate(due, i18n.language) })}</bdi>
            ) : (
              t("phone.noNext")
            )}
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2">
        <div role="radiogroup" aria-label={t("phone.channelLabel")} className="inline-flex overflow-hidden rounded-full border border-line bg-surface text-sm">
          {(["sms", "whatsapp"] as const).map((l) => (
            <button
              key={l}
              type="button"
              role="radio"
              aria-checked={look === l}
              onClick={() => onLook(l)}
              className={cx("min-h-9 px-3 font-semibold", look === l ? "bg-accent text-white" : "text-ink hover:bg-surface-2")}
            >
              {t(`phone.${l}`)}
            </button>
          ))}
        </div>
        <SimulatedTag label={t("phone.simulated")} />
      </div>
    </div>
  );
}

function Bubble({ m, wa, lng }: { m: MessageOut; wa: boolean; lng: string }) {
  const { t } = useTranslation("patient");
  const mine = m.direction === "IN";
  return (
    <li className={cx("flex flex-col", mine ? "items-end" : "items-start")}>
      <div
        className={cx(
          "max-w-[85%] whitespace-pre-line rounded-2xl px-3 py-2 text-[0.95rem] leading-snug",
          mine ? "bg-accent text-white" : wa ? "bg-surface text-ink shadow-card" : "border border-line bg-surface text-ink",
          mine ? "rounded-ee-sm" : "rounded-es-sm",
        )}
      >
        <bdi>{m.text}</bdi>
      </div>
      <span className="mt-0.5 px-1 text-xs text-muted">
        <bdi>{shortTime(m.created_at, lng)}</bdi>
        {mine ? ` · ${t("phone.you")}` : ""}
        {wa && mine ? ` · ${t("phone.delivered")}` : ""}
      </span>
    </li>
  );
}

function QuickReplies({ state, onPick, disabled }: { state: string; onPick: (v: string) => void; disabled: boolean }) {
  const { t } = useTranslation("patient");
  const chips: { send: string; label: string }[] = [];
  if (state === "NOTIFIED") chips.push({ send: "1", label: t("phone.quick.understood") });
  if (state === "ACKNOWLEDGED") chips.push({ send: "150/95", label: t("phone.quick.reading") });
  if (state === "IN_CARE") {
    chips.push({ send: "A", label: t("phone.quick.done") });
    chips.push({ send: "B", label: t("phone.quick.partly") });
    chips.push({ send: "C", label: t("phone.quick.missed") });
  }
  if (state !== "CLOSED") chips.push({ send: "2", label: t("phone.quick.callMe") });
  if (chips.length === 0) return null;
  return (
    <div role="group" aria-label={t("phone.quickLabel")} className="mb-2 flex flex-wrap gap-2">
      {chips.map((ch) => (
        <button
          key={ch.send}
          type="button"
          disabled={disabled}
          onClick={() => onPick(ch.send)}
          className="min-h-9 rounded-full border border-accent bg-accent-soft px-3 text-sm font-semibold text-accent-ink hover:bg-surface-2 disabled:opacity-60"
        >
          <bdi>{ch.label}</bdi>
        </button>
      ))}
    </div>
  );
}
