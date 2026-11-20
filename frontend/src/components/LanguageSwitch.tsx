import { useTranslation } from "react-i18next";
import { LANGUAGES, type Language } from "@/config";
import { setLanguage } from "@/i18n";
import { cx } from "@/lib/cx";

const NAMES: Record<Language, string> = { en: "English", ar: "العربية", fr: "Français" };
const SHORT: Record<Language, string> = { en: "EN", ar: "ع", fr: "FR" };

export interface LanguageSwitchProps {
  className?: string;
  /** Kept for compatibility. The switch is always three compact segments. */
  compact?: boolean;
  /** Dark variant for the demo strip. */
  onDark?: boolean;
}

/** Three compact segments (EN, ع, FR) with full names for assistive technology. */
export function LanguageSwitch({ className, onDark }: LanguageSwitchProps) {
  const { t, i18n } = useTranslation();
  return (
    <div
      role="group"
      aria-label={t("demo.language")}
      className={cx("inline-flex rounded-lg border p-0.5", onDark ? "border-demo-line" : "border-line-strong bg-surface", className)}
    >
      {LANGUAGES.map((lng) => {
        const active = i18n.language === lng;
        return (
          <button
            key={lng}
            type="button"
            lang={lng}
            aria-pressed={active}
            aria-label={NAMES[lng]}
            title={NAMES[lng]}
            onClick={() => setLanguage(lng)}
            className={cx(
              "min-h-8 min-w-9 rounded-md px-2 text-xs font-semibold",
              active
                ? onDark
                  ? "bg-demo-ink text-demo"
                  : "bg-accent text-white"
                : onDark
                  ? "text-demo-ink hover:bg-white/10"
                  : "text-ink hover:bg-surface-2",
            )}
          >
            {SHORT[lng]}
          </button>
        );
      })}
    </div>
  );
}
