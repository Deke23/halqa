import { useTranslation } from "react-i18next";

/** Translated labels for server codes. Unknown codes fall back to a readable form of the code. */
export function useLabels() {
  const { t } = useTranslation("staff");
  const pretty = (s: string) => {
    const x = s.toLowerCase().replace(/_/g, " ");
    return x.charAt(0).toUpperCase() + x.slice(1);
  };
  return {
    nextStep: (key: string | null | undefined) => (key ? t(`nextStep.${key}`, { defaultValue: pretty(key) }) : t("nextStep.none")),
    reason: (code: string) => t(`reasons.${code}`, { defaultValue: pretty(code) }),
    event: (type: string) => t(`events.${type}`, { defaultValue: pretty(type) }),
    task: (key: string) => t(`tasks.${key}`, { defaultValue: pretty(key) }),
    evidence: (type: string) => t(`evidence.${type}`, { defaultValue: pretty(type) }),
    template: (id: string) => {
      const sms = id.endsWith("_sms");
      const base = sms ? id.slice(0, -4) : id;
      const name = t(`templates.${base}`, { defaultValue: pretty(base) });
      return sms ? t("templates.smsSuffix", { name }) : name;
    },
    source: (s: string) => t(`readingSource.${s}`, { defaultValue: pretty(s) }),
    consent: (p: string) => t(`consentPurpose.${p}`, { defaultValue: pretty(p) }),
    planAction: (k: string) => t(`planAction.${k}`, { defaultValue: pretty(k) }),
  };
}
