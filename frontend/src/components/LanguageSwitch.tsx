import { useTranslation } from "react-i18next";
import { LANGUAGES, type Language } from "@/config";
import { setLanguage } from "@/i18n";
import { cx } from "@/lib/cx";

const NAMES: Record<Language, string> = { en: "English", ar: "العربية", fr: "Français" };
const SHORT: Record<Language, string> = { en: "EN", ar: "ع", fr: "FR" };

export interface LanguageSwitchProps {
  className?: string;
  /** Show the short code instead of the full name. */
  compact?: boolean;
}

/** Switches the UI language and flips lang and dir on the html element. */
export function LanguageSwitch({ className, compact }: LanguageSwitchProps) {
  const { t, i18n } = useTranslation();
  return (
    <div role="group" aria-label={t("demo.language")} className={cx("inline-flex rounded-lg border border-line bg-surface p-0.5", className)}>
      {LANGUAGES.map((lng) => {
        const active = i18n.language === lng;
        return (
          <button
            key={lng}
            type="button"
            lang={lng}
            aria-pressed={active}
            aria-label={NAMES[lng]}
            onClick={() => setLanguage(lng)}
            className={cx(
              "min-h-9 min-w-9 rounded-md px-2.5 text-sm font-medium",
              active ? "bg-accent text-white" : "text-ink hover:bg-surface-2",
            )}
          >
            {compact ? SHORT[lng] : NAMES[lng]}
          </button>
        );
      })}
    </div>
  );
}
