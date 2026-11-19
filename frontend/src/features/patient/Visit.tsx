import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, EmptyState, ErrorState, Loading, SimulatedTag, useErrorText, useToast } from "@/components";
import { formatNumber } from "@/lib/format";
import { cx } from "@/lib/cx";
import { formatLocal, usePatientAction, usePatientSlots, useRegionZone, type SlotOut } from "./api";
import { Notice, PageTitle, useCurrentCase } from "./ui";

export default function Visit() {
  const { t, i18n } = useTranslation("patient");
  const c = useCurrentCase();
  const tz = useRegionZone(c.region);
  const accepted = c.state === "REFERRED" && c.referral_status === "ACCEPTED";
  const toName = c.referral?.to_name ?? null;

  let statusKey: string;
  let params: Record<string, string> = {};
  if (c.state === "IN_CARE" || c.state === "CLOSED") statusKey = "inCare";
  else if (c.state === "APPOINTMENT_BOOKED") statusKey = "booked";
  else if (accepted) {
    statusKey = toName ? "accepted" : "acceptedNoName";
    params = { name: toName ?? "" };
  } else if (c.state === "REFERRED") {
    statusKey = toName ? "pending" : "pendingNoName";
    params = { name: toName ?? "" };
  } else if (c.state === "CONFIRMED") statusKey = c.referral_status === "REJECTED" ? "rejected" : "confirmed";
  else statusKey = "early";

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>{t("visit.heading")}</PageTitle>
      <Card title={t("visit.statusTitle")}>
        <div className="flex flex-col gap-2">
          <p className="m-0 text-lg">{t(`visit.status.${statusKey}`, params)}</p>
          {c.referral && c.state !== "CONFIRMED" && c.referral.to_name && (
            <p className="m-0 text-sm text-muted">
              {t("visit.referralTo")}: <bdi>{c.referral.to_name}</bdi>
            </p>
          )}
        </div>
      </Card>

      {c.appointment && (
        <Card title={t("visit.bookedTitle")}>
          <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
            <dt className="text-muted">{t("visit.when")}</dt>
            <dd className="m-0 font-medium">
              <bdi>{formatLocal(c.appointment.starts_at, i18n.language, tz)}</bdi>
            </dd>
            <dt className="text-muted">{t("visit.with")}</dt>
            <dd className="m-0 font-medium">
              <bdi>{c.appointment.provider_name}</bdi>
            </dd>
            <dt className="text-muted">{t("visit.where")}</dt>
            <dd className="m-0 font-medium">
              <bdi>{c.appointment.location}</bdi>
            </dd>
          </dl>
          {c.state === "APPOINTMENT_BOOKED" && <p className="mb-0 mt-3 text-sm text-muted">{t("visit.afterVisit")}</p>}
        </Card>
      )}

      {accepted && <SlotPicker />}
    </div>
  );
}

function CoverLine({ slot }: { slot: SlotOut }) {
  const { t, i18n } = useTranslation("patient");
  const cv = slot.cover;
  const money = (n: number) => `${formatNumber(n, i18n.language, { maximumFractionDigits: 2 })} ${cv.currency}`;
  const headline = cv.covered === true ? t("visit.covered") : cv.covered === false ? t("visit.notCovered") : t("visit.coverUnknown");
  return (
    <div className="mt-2 flex flex-col gap-1 rounded-md bg-surface-2 p-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{headline}</span>
        <SimulatedTag />
      </div>
      <span>
        <bdi>{cv.copay === null ? "" : cv.copay === 0 ? t("visit.noCopay") : t("visit.copay", { amount: money(cv.copay) })}</bdi>
      </span>
      {cv.estimated_price !== null && (
        <span className="text-muted">
          <bdi>{t("visit.price", { amount: money(cv.estimated_price) })}</bdi>
        </span>
      )}
    </div>
  );
}

function SlotPicker() {
  const { t, i18n } = useTranslation("patient");
  const toast = useToast();
  const errorText = useErrorText();
  const c = useCurrentCase();
  const tz = useRegionZone(c.region);
  const slots = usePatientSlots(c.id, true);
  const act = usePatientAction(c.id);
  const [slotId, setSlotId] = useState<number | null>(null);
  const [tried, setTried] = useState(false);

  const book = () => {
    setTried(true);
    if (slotId === null) return;
    act.mutate(
      { action: "book_appointment", payload: { slot_id: slotId } },
      { onSuccess: () => toast.show(t("visit.bookedToast")), onError: (e) => toast.show(errorText(e), "due") },
    );
  };

  return (
    <Card title={t("visit.slotsTitle")}>
      {slots.isLoading ? (
        <Loading />
      ) : slots.error ? (
        <ErrorState error={slots.error} onRetry={() => void slots.refetch()} />
      ) : !slots.data || slots.data.length === 0 ? (
        <EmptyState description={t("visit.slotsEmpty")} />
      ) : (
        <fieldset className="m-0 flex min-w-0 flex-col gap-3 border-0 p-0">
          <legend className="mb-2 text-sm font-medium">{t("visit.slotsLegend")}</legend>
          {slots.data.map((s) => {
            const checked = slotId === s.id;
            return (
              <label
                key={s.id}
                className={cx(
                  "flex cursor-pointer items-start gap-3 rounded-lg border p-3",
                  checked ? "border-accent bg-accent-soft" : "border-line bg-surface hover:bg-surface-2",
                )}
              >
                <input
                  type="radio"
                  name="slot"
                  value={s.id}
                  checked={checked}
                  onChange={() => setSlotId(s.id)}
                  className="mt-1 size-4 accent-[var(--color-accent)]"
                />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="font-semibold">
                    <bdi>{formatLocal(s.starts_at, i18n.language, tz)}</bdi>
                  </span>
                  <span className="text-sm">
                    <bdi>{s.provider_name}</bdi>
                  </span>
                  <span className="text-sm text-muted">
                    <bdi>{s.location}</bdi>
                  </span>
                  <CoverLine slot={s} />
                </span>
              </label>
            );
          })}
          <p className="m-0 text-sm text-muted">{t("visit.coverNote")}</p>
          {tried && slotId === null && (
            <p role="alert" className="m-0 text-sm font-medium text-due-ink">
              {t("visit.pickFirst")}
            </p>
          )}
          <Button size="lg" fullWidth loading={act.isPending} onClick={book}>
            {t("visit.book")}
          </Button>
        </fieldset>
      )}
      {act.isError && <Notice tone="due">{errorText(act.error)}</Notice>}
    </Card>
  );
}
