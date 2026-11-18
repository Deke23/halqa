import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "@/config";
import { useAuth } from "@/api/auth";
import { api } from "@/api/client";
import { PERSONAS, type Persona } from "@/api/types";
import { setLanguage } from "@/i18n";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { ErrorState } from "@/components/States";
import { Tag, SimulatedTag } from "@/components/Tag";
import { useToast } from "@/components/Toast";
import { useErrorText } from "@/components/States";
import { PERSONA_META } from "./personas";

/** Landing page: "Continue as Guest", then the persona picker, plus "Reset demo data". Works without the backend. */
export default function Landing() {
  const { t } = useTranslation();
  const { loginAsGuest, isSignedIn, logout } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const toast = useToast();
  const errorText = useErrorText();
  const picking = params.get("pick") === "1";

  const [busy, setBusy] = useState<Persona | null>(null);
  const [loginError, setLoginError] = useState<unknown>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [resetting, setResetting] = useState(false);

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
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-4 py-6 md:py-10">
      <header className="mb-8 flex items-center justify-between gap-3">
        <span className="text-2xl font-bold text-accent-ink">{APP_NAME}</span>
        <LanguageSwitch />
      </header>

      <main className="flex-1">
        <section className="max-w-2xl">
          <h1 className="text-3xl font-semibold leading-tight md:text-4xl">{t("landing.title")}</h1>
          <p className="mt-3 text-lg text-muted">{t("app.tagline")}</p>
          <p className="mt-3 flex flex-wrap items-center gap-2 text-muted">
            <SimulatedTag label={t("demo.simulatedData")} />
            <span>{t("landing.intro")}</span>
          </p>

          {!picking && (
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Button size="lg" onClick={() => setParams({ pick: "1" })}>
                {t("landing.continueGuest")}
              </Button>
              <Link to="/transparency" className="font-medium text-accent-ink underline underline-offset-2">
                {t("landing.openTransparency")}
              </Link>
            </div>
          )}
        </section>

        {picking && (
          <section aria-labelledby="persona-heading" className="mt-8">
            <h2 id="persona-heading" className="text-xl font-semibold">
              {t("landing.pickPersona")}
            </h2>
            <p className="mt-1 text-muted">{t("landing.pickPersonaHint")}</p>

            {loginError != null && (
              <div className="mt-4">
                <ErrorState
                  title={t("landing.loginFailed")}
                  error={loginError}
                  onRetry={() => setLoginError(null)}
                />
              </div>
            )}

            <ul className="mt-4 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {PERSONAS.map((p) => {
                const meta = PERSONA_META[p];
                return (
                  <li key={p}>
                    <Card as="div" className="flex h-full flex-col">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-lg font-semibold">{t(`personas.${p}.name`)}</p>
                          <p className="text-sm text-muted">{t(`personas.${p}.role`)}</p>
                        </div>
                        <Tag>{t(`regions.${meta.region}`)}</Tag>
                      </div>
                      <p className="mt-2 flex-1 text-sm">{t(`personas.${p}.description`)}</p>
                      <Button
                        className="mt-4"
                        fullWidth
                        loading={busy === p}
                        disabled={busy !== null}
                        onClick={() => void choose(p)}
                      >
                        {busy === p ? t("landing.signingIn") : t("landing.signInAs", { name: t(`personas.${p}.name`) })}
                      </Button>
                    </Card>
                  </li>
                );
              })}
            </ul>

            <div className="mt-6">
              <Button variant="secondary" onClick={() => setConfirmReset(true)}>
                {t("demo.reset")}
              </Button>
            </div>
          </section>
        )}
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
