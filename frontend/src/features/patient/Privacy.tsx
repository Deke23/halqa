import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, ConfirmDialog, useErrorText, useToast } from "@/components";
import { usePatientAction, type ConsentOut } from "./api";
import { BulletList, PageTitle, useCurrentCase } from "./ui";

const ORDER = ["care_coordination", "messaging_channel", "share_with_receiving_provider", "lifestyle_programme", "research_aggregate"];

export default function Privacy() {
  const { t } = useTranslation("patient");
  const toast = useToast();
  const errorText = useErrorText();
  const c = useCurrentCase();
  const act = usePatientAction(c.id);
  const [pending, setPending] = useState<ConsentOut | null>(null);

  const consents = [...c.consents].sort((a, b) => ORDER.indexOf(a.purpose) - ORDER.indexOf(b.purpose));
  const canChange = c.allowed_actions.includes("update_consent");
  const data = t("privacy.data", { returnObjects: true }) as string[];

  const change = (consent: ConsentOut, granted: boolean) =>
    act.mutate(
      { action: "update_consent", payload: { purpose: consent.purpose, granted, channel: consent.channel } },
      {
        onSuccess: () => {
          toast.show(granted ? t("privacy.changedOn") : t("privacy.changedOff"));
          setPending(null);
        },
        onError: (e) => {
          toast.show(errorText(e), "due");
          setPending(null);
        },
      },
    );

  const channelText = (consent: ConsentOut) => (consent.channel ? t(`privacy.channel.${consent.channel}`) : "");

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>{t("privacy.heading")}</PageTitle>

      <Card title={t("privacy.consentTitle")}>
        <p className="mt-0 text-muted">{t("privacy.consentIntro")}</p>
        <ul className="m-0 flex list-none flex-col divide-y divide-line p-0">
          {consents.map((cs) => {
            const id = `consent-${cs.purpose}-${cs.channel ?? "all"}`;
            return (
              <li key={id} className="flex flex-col gap-2 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p id={id} className="m-0 font-medium">
                      {t(`privacy.purpose.${cs.purpose}.name`)}
                    </p>
                    <p className="m-0 text-sm text-muted">{t(`privacy.purpose.${cs.purpose}.text`, { channel: channelText(cs) })}</p>
                  </div>
                  <Badge tone={cs.granted ? "accent" : "neutral"}>{cs.granted ? t("privacy.on") : t("privacy.off")}</Badge>
                </div>
                <div>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!canChange || act.isPending}
                    aria-describedby={id}
                    onClick={() => (cs.granted ? setPending(cs) : change(cs, true))}
                  >
                    {cs.granted ? t("privacy.turnOff") : t("privacy.turnOn")}
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      </Card>

      <Card title={t("privacy.dataTitle")}>
        <BulletList items={data} />
      </Card>

      <ConfirmDialog
        open={pending !== null}
        title={t("privacy.confirmTitle")}
        body={pending ? t(`privacy.purpose.${pending.purpose}.withdraw`, { channel: channelText(pending) }) : ""}
        confirmLabel={t("privacy.confirmButton")}
        loading={act.isPending}
        onConfirm={() => pending && change(pending, false)}
        onCancel={() => setPending(null)}
      />
    </div>
  );
}
