import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "@/config";
import { useAuth } from "@/api/auth";
import { useAdvanceClock, useDemoClock, useResetDemo } from "@/api/hooks";
import { formatDateTime } from "@/lib/format";
import { Button } from "./Button";
import { ConfirmDialog } from "./ConfirmDialog";
import { LanguageSwitch } from "./LanguageSwitch";
import { SimulatedTag } from "./Tag";
import { useToast } from "./Toast";
import { useErrorText } from "./States";

/**
 * Persistent demo bar: persona, switch persona, demo clock with +1 day and +3 days,
 * "Simulated data" tag, language switch. Rendered once by AppShell for every signed-in screen.
 */
export function DemoBar() {
  const { t, i18n } = useTranslation();
  const { user, persona } = useAuth();
  const clock = useDemoClock();
  const advance = useAdvanceClock();
  const reset = useResetDemo();
  const toast = useToast();
  const errorText = useErrorText();
  const [confirmReset, setConfirmReset] = useState(false);

  function move(hours: number) {
    advance.mutate(
      { hours },
      {
        onSuccess: () => toast.show(t("demo.clockAdvanced")),
        onError: (e) => toast.show(errorText(e), "due"),
      },
    );
  }

  return (
    <div role="region" aria-label={t("demo.bar")} className="sticky top-0 z-40 border-b border-line bg-surface">
      <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 text-sm">
        <Link to="/" className="font-semibold text-accent-ink">
          {APP_NAME}
        </Link>
        <SimulatedTag label={t("demo.simulatedData")} />

        <div className="flex items-center gap-2">
          <span className="text-muted">{t("demo.persona")}</span>
          <strong>{persona ? t(`personas.${persona}.name`) : user?.name}</strong>
          {persona && <span className="text-muted">({t(`personas.${persona}.role`)})</span>}
          <Link to="/?pick=1" className="font-medium text-accent-ink underline underline-offset-2">
            {t("demo.switchPersona")}
          </Link>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-muted">{t("demo.clock")}</span>
          <time className="font-medium latin-digits" dateTime={clock.data?.now}>
            {clock.data?.now ? formatDateTime(clock.data.now, i18n.language) : "-"}
          </time>
          <Button size="sm" variant="secondary" onClick={() => move(24)} loading={advance.isPending}>
            {t("demo.plus1Day")}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => move(72)} loading={advance.isPending}>
            {t("demo.plus3Days")}
          </Button>
        </div>

        <div className="ms-auto flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={() => setConfirmReset(true)}>
            {t("demo.reset")}
          </Button>
          <LanguageSwitch compact />
        </div>
      </div>

      <ConfirmDialog
        open={confirmReset}
        title={t("demo.resetConfirmTitle")}
        body={t("demo.resetConfirmBody")}
        confirmLabel={t("demo.reset")}
        loading={reset.isPending}
        onCancel={() => setConfirmReset(false)}
        onConfirm={() =>
          reset.mutate(undefined, {
            onSuccess: () => {
              setConfirmReset(false);
              toast.show(t("demo.resetDone"));
            },
            onError: (e) => {
              setConfirmReset(false);
              toast.show(errorText(e), "due");
            },
          })
        }
      />
    </div>
  );
}
