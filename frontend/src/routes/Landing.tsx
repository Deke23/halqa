import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { api } from "@/api/client";
import { CASE_STATES, type Persona } from "@/api/types";
import { setLanguage } from "@/i18n";
import { Brand } from "@/components/Brand";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { LoopRing } from "@/components/LoopRing";
import { ErrorState, useErrorText } from "@/components/States";
import { useToast } from "@/components/Toast";
import { cx } from "@/lib/cx";
import { PERSONA_META } from "./personas";

const GROUPS: Array<{ key: "abu_dhabi" | "yaounde" | "all"; personas: Persona[] }> = [
  { key: "abu_dhabi", personas: ["patient_auh", "coordinator_auh", "clinician_pcp", "clinician_specialist"] },
  { key: "yaounde", personas: ["patient_yde", "nurse_yde"] },
  { key: "all", personas: ["analyst"] },
];

/** Steps shown as reached in the landing illustration. The next one breathes. */
const DEMO_REACHED = 3;

/** Landing page: the idea in five seconds, then "Continue as Guest" and the persona picker. Works without the backend. */
export default function Landing() {
  const { t } = useTranslation();
  const { loginAsGuest, isSignedIn, logout } = useAuth();
  const navigate = useNavigate();
  const [, setParams] = useSearchParams();
  const toast = useToast();
  const errorText = useErrorText();
  // The personas are always listed; "Continue as Guest" in the hero scrolls to them.
  const picking: boolean = true;
  const pickerRef = useRef<HTMLElement>(null);

  const [busy, setBusy] = useState<Persona | null>(null);
  const [loginError, setLoginError] = useState<unknown>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [resetting, setResetting] = useState(false);

  function startPicking() {
    setParams({ pick: "1" });
    window.setTimeout(() => pickerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }

  async function choose(p: Persona) {
    setBusy(p);
    setLoginError(null);
    try {
      await loginAsGuest(p);
      setLanguage(PERSONA_META[p].language);
      navigate(PERSONA_META[p].home);
    } catch (e) {
      setLoginError(e);
    } finally {
      setBusy(null);
    }
  }

  async function resetDemo() {
    setResetting(true);
    try {
      // Reset needs a token. If nobody is signed in, sign in as the analyst, reset, sign out again.
      let temporary = false;
      if (!isSignedIn) {
        await loginAsGuest("analyst");
        temporary = true;
      }
      await api("/demo/reset", { method: "POST" });
      if (temporary) logout();
      toast.show(t("demo.resetDone"));
    } catch (e) {
      toast.show(errorText(e), "due");
    } finally {
      setResetting(false);
      setConfirmReset(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 pb-16 pt-5 sm:px-8">
      <header className="flex items-center justify-between gap-3">
        <Brand size={30} />
        <LanguageSwitch />
      </header>

      <main className="flex-1">
        <section className="grid items-center gap-10 py-10 md:py-16 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
          <div className="rise-in">
            <p className="mb-4 inline-flex items-center gap-2 rounded-md border border-dashed border-info-ink/55 bg-info-soft px-2 py-1 text-xs font-medium text-info-ink">
              <span aria-hidden="true" className="size-1.5 rounded-full bg-info-ink" />
              {t("landing.simulatedNotice")}
            </p>
            <h1 className="text-4xl font-semibold leading-[1.08] sm:text-5xl">{t("landing.title")}</h1>
            <p className="mt-5 max-w-xl text-lg text-muted">{t("landing.lead")}</p>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
              <Button size="lg" onClick={startPicking}>
                {t("landing.continueGuest")}
              </Button>
              <Link to="/transparency" className="min-h-11 content-center font-medium text-accent-ink underline underline-offset-4">
                {t("landing.openTransparency")}
              </Link>
              <button
                type="button"
                onClick={() => void choose("analyst")}
                className="min-h-11 font-medium text-accent-ink underline underline-offset-4"
              >
                {t("landing.openDashboard")}
              </button>
            </div>
          </div>

          <div className="rise-in flex flex-col items-center gap-8 rounded-sheet border border-line bg-surface p-6 sm:flex-row sm:p-8 lg:p-10">
            <LoopRing reached={DEMO_REACHED} size={220} thickness={18} label={t("landing.ringLabel", { n: DEMO_REACHED + 1 })}>
              <span className="flex flex-col items-center leading-none">
                <span className="readout text-4xl font-semibold">
                  {DEMO_REACHED}/{CASE_STATES.length}
                </span>
                <span className="mt-2 text-xs text-muted">{t("landing.ringCaption")}</span>
              </span>
            </LoopRing>
            <ol className="m-0 grid w-full list-none gap-2.5 p-0 text-sm">
              {CASE_STATES.map((s, i) => {
                const reached = i < DEMO_REACHED;
                const current = i === DEMO_REACHED;
                return (
                  <li key={s} className={cx("flex items-center gap-3", !reached && !current && "text-muted")}>
                    <span aria-hidden="true" className="grid size-4 shrink-0 place-items-center">
                      {reached && <span className="size-2.5 rounded-full bg-accent" />}
                      {current && <span className="loop-ring-current size-2.5 rounded-full bg-accent" />}
                      {!reached && !current && <span className="size-2.5 rounded-full border-[1.5px] border-line-strong" />}
                    </span>
                    <span className={cx(current && "font-semibold text-ink")}>{t(`states.${s}`)}</span>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>

        <section ref={pickerRef} aria-labelledby="persona-heading" className="scroll-mt-4 border-t border-line pt-10">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id="persona-heading" className="text-2xl font-semibold">
                {t("landing.pickPersona")}
              </h2>
              <p className="mt-1 text-muted">{t("landing.pickPersonaHint")}</p>
            </div>
            <Button variant="secondary" size="sm" onClick={() => setConfirmReset(true)}>
              {t("demo.reset")}
            </Button>
          </div>

          {!picking && (
            <p className="mt-6">
              <Button variant="secondary" onClick={startPicking}>
                {t("landing.continueGuest")}
              </Button>
            </p>
          )}

          {picking && loginError != null && (
            <div className="mt-5">
              <ErrorState title={t("landing.loginFailed")} error={loginError} onRetry={() => setLoginError(null)} />
            </div>
          )}

          {picking &&
            GROUPS.map((g) => (
              <div key={g.key} className="mt-8">
                <h3 className="mb-3 text-sm font-semibold text-muted">{t(`regions.${g.key}`)}</h3>
                <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-4">
                  {g.personas.map((p) => (
                    <li key={p} className="flex">
                      <div className="rise-in flex w-full flex-col rounded-card border border-line bg-surface p-5">
                        <div className="flex items-center gap-3">
                          <span
                            aria-hidden="true"
                            className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-base font-semibold text-accent-ink"
                          >
                            {Array.from(t(`personas.${p}.name`))[0]}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate text-lg font-semibold leading-tight">{t(`personas.${p}.name`)}</p>
                            <p className="text-sm text-muted">{t(`personas.${p}.role`)}</p>
                          </div>
                        </div>
                        <p className="mt-3 flex-1 text-sm text-muted">{t(`personas.${p}.description`)}</p>
                        <Button
                          className="mt-4"
                          fullWidth
                          loading={busy === p}
                          disabled={busy !== null}
                          onClick={() => void choose(p)}
                        >
                          {busy === p ? t("landing.signingIn") : t("landing.signInAs", { name: t(`personas.${p}.name`) })}
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
        </section>
      </main>

      <ConfirmDialog
        open={confirmReset}
        title={t("demo.resetConfirmTitle")}
        body={t("demo.resetConfirmBody")}
        confirmLabel={t("demo.reset")}
        loading={resetting}
        onCancel={() => setConfirmReset(false)}
        onConfirm={() => void resetDemo()}
      />
    </div>
  );
}
