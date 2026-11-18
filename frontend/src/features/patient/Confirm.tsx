import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Badge, BPReading, Button, Card, EmptyState, Field, Input, RadioGroup, Tag, useErrorText, useToast } from "@/components";
import { useDemoClock } from "@/api/hooks";
import { formatDateTime } from "@/lib/format";
import { homeReadingDays, useDiary, usePatientAction, type PatientCase } from "./api";
import { Notice, PageTitle, useCurrentCase } from "./ui";

const TOTAL_DAYS = 7;
const linkBtn =
  "inline-flex min-h-11 items-center justify-center rounded-lg bg-accent px-4 py-2 font-semibold text-white hover:bg-accent-strong";

/** datetime-local value in UTC, because the demo clock and the rest of the app are shown in UTC. */
function toLocalInput(d: Date): string {
  return d.toISOString().slice(0, 16);
}

export default function Confirm() {
  const { t } = useTranslation("patient");
  const c = useCurrentCase();

  if (c.state === "RESULT_ISSUED" || c.state === "NOTIFIED") {
    return (
      <div className="flex flex-col gap-4">
        <PageTitle>{t("confirm.heading")}</PageTitle>
        <Notice>{t("confirm.needUnderstand")}</Notice>
        <Link to="/patient/understand" className={linkBtn}>
          {t("confirm.toUnderstand")}
        </Link>
      </div>
    );
  }

  const conf = c.confirmation;
  const method = conf?.method ?? null;
  const reviewed = c.state !== "ACKNOWLEDGED";
  const notConfirmed = c.state === "ACKNOWLEDGED" && c.next_step?.label_key === "clinician_closure_decision";

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>{t("confirm.heading")}</PageTitle>
      {reviewed && <Notice tone="accent">{t("confirm.reviewed")}</Notice>}
      {notConfirmed && <Notice>{t("confirm.notConfirmed")}</Notice>}
      {!reviewed && <MethodChoice caseId={c.id} method={method} />}
      {method === "HBPM" && <Readings c={c} locked={reviewed} />}
      {method === "ABPM" && !reviewed && (
        <Card>
          <p>{t("confirm.abpmBody")}</p>
        </Card>
      )}
    </div>
  );
}

function MethodChoice({ caseId, method }: { caseId: number; method: "HBPM" | "ABPM" | null }) {
  const { t } = useTranslation("patient");
  const toast = useToast();
  const errorText = useErrorText();
  const act = usePatientAction(caseId);
  const [choice, setChoice] = useState<string>(method ?? "");
  const changed = choice !== "" && choice !== method;

  const body = (
      <div className="flex flex-col gap-3">
        <RadioGroup
          name="method"
          legend={t("confirm.legend")}
          value={choice}
          onChange={setChoice}
          options={[
            { value: "HBPM", label: t("confirm.hbpm"), description: t("confirm.hbpmHelp") },
            { value: "ABPM", label: t("confirm.abpm"), description: t("confirm.abpmHelp") },
          ]}
        />
        <Button
          disabled={!changed}
          loading={act.isPending}
          onClick={() =>
            act.mutate(
              { action: "choose_confirmation", payload: { method: choice } },
              { onSuccess: () => toast.show(t("confirm.saved")), onError: (e) => toast.show(errorText(e), "due") },
            )
          }
        >
          {t("confirm.save")}
        </Button>
      </div>
  );
  if (method === null) return <Card title={t("confirm.chooseTitle")}>{body}</Card>;
  return (
    <details className="rounded-card border border-line bg-surface shadow-card">
      <summary className="flex min-h-11 cursor-pointer items-center justify-between gap-2 px-4 py-2 font-medium">
        <span>{t("confirm.chosen", { method: t(method === "HBPM" ? "confirm.hbpm" : "confirm.abpm") })}</span>
        <span className="text-sm text-accent-ink underline">{t("confirm.change")}</span>
      </summary>
      <div className="px-4 pb-4">{body}</div>
    </details>
  );
}

function Readings({ c, locked }: { c: PatientCase; locked: boolean }) {
  const { t, i18n } = useTranslation("patient");
  const toast = useToast();
  const errorText = useErrorText();
  const act = usePatientAction(c.id);
  const clock = useDemoClock();
  const diary = useDiary();

  const [sys, setSys] = useState("");
  const [dia, setDia] = useState("");
  const [pulse, setPulse] = useState("");
  const [when, setWhen] = useState("");
  const [tried, setTried] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);

  const nowIso = clock.data?.now ?? new Date().toISOString();
  const whenValue = when || toLocalInput(new Date(nowIso));

  const s = Number(sys);
  const d = Number(dia);
  const p = Number(pulse);
  const errors = {
    sys: !Number.isInteger(s) || s < 60 || s > 260 ? t("confirm.errSystolic") : null,
    dia: !Number.isInteger(d) || d < 30 || d > 160 ? t("confirm.errDiastolic") : null,
    order: !(s > d) ? t("confirm.errOrder") : null,
    pulse: pulse !== "" && (!Number.isInteger(p) || p < 30 || p > 220) ? t("confirm.errPulse") : null,
    when: !whenValue ? t("confirm.errWhen") : null,
  };
  const invalid = Object.values(errors).some(Boolean);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (invalid) return;
    act.mutate(
      {
        action: "add_reading",
        payload: {
          systolic: s,
          diastolic: d,
          pulse: pulse === "" ? null : p,
          taken_at: `${whenValue}:00Z`,
          source: "HOME_CUFF",
        },
      },
      {
        onSuccess: () => {
          toast.show(t("confirm.added"));
          setSys("");
          setDia("");
          setPulse("");
          setTried(false);
        },
        onError: (err) => toast.show(errorText(err), "due"),
      },
    );
  };

  /** Loads the sample series from the diary endpoint, one real add_reading per value, dated relative to the demo clock. */
  const fillSample = async () => {
    if (!diary.data) return;
    setLoadingSample(true);
    try {
      const now = new Date(nowIso);
      const todayUtc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
      const days = Math.max(...diary.data.hbpm_sample.map((r) => r.day));
      let n = 0;
      for (const r of diary.data.hbpm_sample) {
        const [hh, mm] = r.time.split(":").map(Number);
        const at = new Date(todayUtc - (days - r.day + 1) * 86_400_000 + (hh! * 60 + mm!) * 60_000);
        await act.mutateAsync({
          action: "add_reading",
          payload: { systolic: r.systolic, diastolic: r.diastolic, pulse: r.pulse ?? null, taken_at: at.toISOString(), source: "HOME_CUFF" },
        });
        n += 1;
      }
      toast.show(t("confirm.demoDone", { n }));
    } catch (e) {
      toast.show(errorText(e), "due");
    } finally {
      setLoadingSample(false);
    }
  };

  const home = c.readings.filter((r) => r.source === "HOME_CUFF").sort((a, b) => b.taken_at.localeCompare(a.taken_at));
  const dayCount = Math.min(homeReadingDays(c.readings), TOTAL_DAYS);
  const conf = c.confirmation;
  const how = t("confirm.how", { returnObjects: true }) as string[];

  return (
    <>
      {!locked && (
        <Card title={t("confirm.howTitle")}>
          <ol className="m-0 flex flex-col gap-1.5 ps-5">
            {how.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ol>
        </Card>
      )}

      <Card title={t("confirm.progressTitle")}>
        <div className="flex flex-col gap-3">
          <p className="text-lg font-semibold">
            <bdi>{t("confirm.dayOf", { n: dayCount, total: TOTAL_DAYS })}</bdi>
          </p>
          <div
            role="progressbar"
            aria-label={t("confirm.progressLabel")}
            aria-valuemin={0}
            aria-valuemax={TOTAL_DAYS}
            aria-valuenow={dayCount}
            className="h-3 w-full overflow-hidden rounded-full bg-surface-2"
          >
            <div className="h-full bg-accent" style={{ width: `${(dayCount / TOTAL_DAYS) * 100}%` }} />
          </div>
          <p className="text-sm text-muted">{t("confirm.needed", { days: conf?.days_required ?? 4 })}</p>
          <div>
            <p className="m-0 text-sm font-medium text-muted">{t("confirm.averageTitle")}</p>
            {conf && conf.average_systolic !== null && conf.average_diastolic !== null ? (
              <>
                <BPReading systolic={conf.average_systolic} diastolic={conf.average_diastolic} size="md" />
                <p className="m-0 text-sm text-muted">{t("confirm.averageBasis", { n: conf.readings_used })}</p>
              </>
            ) : (
              <p className="m-0 text-muted">{t("confirm.averageNone")}</p>
            )}
          </div>
          {!locked && conf?.status === "CONFIRMED_RAISED" && <Notice tone="accent">{t("confirm.enough")}</Notice>}
        </div>
      </Card>

      {!locked && (
        <Card title={t("confirm.formTitle")}>
          <form onSubmit={submit} noValidate className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("confirm.systolic")} error={tried ? errors.sys : null} required>
                <Input inputMode="numeric" value={sys} onChange={(e) => setSys(e.target.value)} autoComplete="off" dir="ltr" />
              </Field>
              <Field label={t("confirm.diastolic")} error={tried ? (errors.dia ?? errors.order) : null} required>
                <Input inputMode="numeric" value={dia} onChange={(e) => setDia(e.target.value)} autoComplete="off" dir="ltr" />
              </Field>
            </div>
            <Field label={t("confirm.pulse")} optional error={tried ? errors.pulse : null}>
              <Input inputMode="numeric" value={pulse} onChange={(e) => setPulse(e.target.value)} autoComplete="off" dir="ltr" />
            </Field>
            <Field label={t("confirm.when")} error={tried ? errors.when : null}>
              <Input type="datetime-local" value={whenValue} onChange={(e) => setWhen(e.target.value)} dir="ltr" />
            </Field>
            <Button type="submit" loading={act.isPending && !loadingSample}>
              {t("confirm.add")}
            </Button>
          </form>
        </Card>
      )}

      {!locked && (
        <Card title={t("confirm.demoTitle")} action={<Tag>{t("shortcuts.badge")}</Tag>} className="border-dashed">
          <div className="flex flex-col gap-3">
            <p className="m-0 text-sm text-muted">{t("confirm.demoText")}</p>
            <Button variant="secondary" loading={loadingSample} disabled={!diary.data || act.isPending} onClick={fillSample}>
              {loadingSample ? t("confirm.demoLoading") : t("confirm.demoButton")}
            </Button>
          </div>
        </Card>
      )}

      <Card title={t("confirm.listTitle")} action={<Badge>{home.length}</Badge>}>
        {home.length === 0 ? (
          <EmptyState description={t("confirm.listEmpty")} />
        ) : (
          <ul className="m-0 flex max-h-72 list-none flex-col divide-y divide-line overflow-y-auto p-0">
            {home.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-3 py-2">
                <BPReading systolic={r.systolic} diastolic={r.diastolic} size="sm" />
                <span className="text-end text-sm text-muted">
                  <bdi>{formatDateTime(r.taken_at, i18n.language)}</bdi>
                  {r.pulse ? (
                    <>
                      {" · "}
                      <bdi>{t("confirm.pulseValue", { n: r.pulse })}</bdi>
                    </>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
