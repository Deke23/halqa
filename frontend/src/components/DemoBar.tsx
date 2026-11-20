import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { useAdvanceClock, useDemoClock, useResetDemo } from "@/api/hooks";
import { formatDateTime } from "@/lib/format";
import { pickText } from "@/lib/i18nField";
import { cx } from "@/lib/cx";
import { Brand } from "./Brand";
import { ConfirmDialog } from "./ConfirmDialog";
import { LanguageSwitch } from "./LanguageSwitch";
import { useToast } from "./Toast";
import { usePersonaText } from "./usePersonaText";
import { useErrorText } from "./States";

function StripButton({ children, className, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cx(
        "inline-flex min-h-8 items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-demo-line px-2.5 text-xs font-medium text-demo-ink",
        "hover:bg-white/10 disabled:cursor-progress disabled:opacity-60",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

/**
 * The demo strip. A slim dark bar that sits in the page flow (it takes real space) and reads as
 * a tool outside the product: Simulated data, persona and switch, demo clock with +1 day and +3 days,
 * reset, language. One line from 1024 px; below that one compact row plus a "Demo" panel.
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
  const [open, setOpen] = useState(false);

  const u = user as { display_names?: Record<string, string>; names?: Record<string, string>; display_name?: string; name?: string } | null;
  const pText = usePersonaText();
  const who =
    pickText(u?.display_names ?? u?.names, u?.display_name ?? u?.name ?? "", i18n.language) ||
    (persona ? pText(persona).name : "");

  function move(hours: number) {
    advance.mutate(
      { hours },
      {
        onSuccess: () => toast.show(t("demo.clockAdvanced")),
        onError: (e) => toast.show(errorText(e), "due"),
      },
    );
  }

  const sep = <span aria-hidden="true" className="hidden h-4 w-px bg-demo-line lg:block" />;

  const simulated: ReactNode = (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-demo-ink">
      <span aria-hidden="true" className="size-1.5 rounded-full bg-[#e0a43a]" />
      {t("demo.simulatedData")}
    </span>
  );

  const clockBlock: ReactNode = (
    <div className="flex items-center gap-2">
      <span className="text-xs text-demo-ink/70">{t("demo.clock")}</span>
      <time className="readout text-xs text-demo-ink" dateTime={clock.data?.now}>
        {clock.data?.now ? formatDateTime(clock.data.now, i18n.language) : "-"}
      </time>
      <StripButton onClick={() => move(24)} disabled={advance.isPending}>
        {t("demo.plus1Day")}
      </StripButton>
      <StripButton onClick={() => move(72)} disabled={advance.isPending}>
        {t("demo.plus3Days")}
      </StripButton>
    </div>
  );

  return (
    <div data-demo-strip role="region" aria-label={t("demo.bar")} className="relative z-40 flex-none bg-demo text-demo-ink">
      <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center gap-x-4 gap-y-2 px-3 py-1.5 sm:px-4">
        <Link to="/" aria-label={t("nav.home")} className="rounded-md">
          <Brand size={20} onDark />
        </Link>
        {sep}

        <div className="flex min-w-0 items-center gap-2 text-xs">
          <span className="hidden text-demo-ink/70 sm:inline">{t("demo.persona")}</span>
          <strong className="truncate font-semibold">{who}</strong>
          <Link to="/?pick=1" className="hidden font-medium underline underline-offset-2 hover:text-white lg:inline">
            {t("demo.switchPersona")}
          </Link>
        </div>

        <div className="hidden items-center gap-4 lg:flex">
          {sep}
          {simulated}
          {sep}
          {clockBlock}
        </div>

        <div className="ms-auto flex items-center gap-2">
          <span className="hidden lg:block">
            <StripButton onClick={() => setConfirmReset(true)}>{t("demo.reset")}</StripButton>
          </span>
          <LanguageSwitch onDark />
          <span className="lg:hidden">
            <StripButton aria-expanded={open} aria-controls="demo-panel" onClick={() => setOpen((v) => !v)}>
              {t("demo.toggle")}
              <span aria-hidden="true" className={cx("inline-block text-[10px] transition-transform", open && "rotate-180")}>
                &#9662;
              </span>
            </StripButton>
          </span>
        </div>

        {open && (
          <div id="demo-panel" className="flex w-full flex-col gap-3 border-t border-demo-line pb-2 pt-3 lg:hidden">
            {simulated}
            {clockBlock}
            <div className="flex flex-wrap gap-2">
              <Link
                to="/?pick=1"
                onClick={() => setOpen(false)}
                className="inline-flex min-h-8 items-center rounded-md border border-demo-line px-2.5 text-xs font-medium hover:bg-white/10"
              >
                {t("demo.switchPersona")}
              </Link>
              <StripButton onClick={() => setConfirmReset(true)}>{t("demo.reset")}</StripButton>
            </div>
          </div>
        )}
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
