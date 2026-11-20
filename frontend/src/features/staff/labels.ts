import { useTranslation } from "react-i18next";
import { pickText, type I18nText } from "@/lib/i18nField";

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
      const plan = /^plan_action_(.+)_(full|smaller|smallest)$/.exec(base);
      const name = plan
        ? t("templates.plan_action", { action: t(`planAction.${plan[1]}`, { defaultValue: pretty(plan[1]!) }), size: t(`plan.size.${plan[2]}`) })
        : t(`templates.${base}`, { defaultValue: pretty(base) });
      return sms ? t("templates.smsSuffix", { name }) : name;
    },
    source: (s: string) => t(`readingSource.${s}`, { defaultValue: pretty(s) }),
    consent: (p: string) => t(`consentPurpose.${p}`, { defaultValue: pretty(p) }),
    /** Job title of a person, translated when known. */
    roleTitle: (title: string | null | undefined, holder?: unknown) => {
      if (!title) return "";
      const map = holder as { roles?: I18nText; role_titles?: I18nText } | null | undefined;
      const fromServer = pickText(map?.roles ?? map?.role_titles, "");
      if (fromServer && fromServer !== title) return fromServer;
      return t(`roleTitle.${title.toLowerCase().replace(/[^a-z]+/g, "_").replace(/^_|_$/g, "")}`, { defaultValue: title });
    },
    contact: (code: string | null | undefined) => (code ? t(`contactAttempt.${code}`, { defaultValue: t(`events.${code}`, { defaultValue: pretty(code) }) }) : ""),
    planAction: (k: string) => t(`planAction.${k}`, { defaultValue: pretty(k) }),
  };
}
