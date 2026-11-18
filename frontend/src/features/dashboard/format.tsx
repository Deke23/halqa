import { useTranslation } from "react-i18next";
import { formatNumber, formatPercent } from "@/lib/format";
import { groupLabelKey, type MeasureKind, type Norm } from "./measures";

/** Text for one measure cell. A suppressed cell never shows a number. */
export function useMeasureText() {
  const { t, i18n } = useTranslation("dashboard");
  const { t: tc } = useTranslation();
  const num = (v: number, d = 1) => formatNumber(v, i18n.language, { maximumFractionDigits: d });
  return (kind: MeasureKind, m: Norm | undefined): string => {
    if (!m) return t("notMeasured");
    if (m.suppressed) return tc("fewerThan5");
    switch (kind) {
      case "time_h":
      case "time_d": {
        if (m.median == null) return t("notMeasured");
        const u = kind === "time_h" ? t("unit.h") : t("unit.d");
        return `${num(m.median)} ${u}` + (m.p90 != null ? ` (${t("p90")} ${num(m.p90)})` : "");
      }
      case "rate":
        return m.value == null ? t("notMeasured") : formatPercent(m.value, i18n.language);
      case "mean":
        return m.value == null ? t("notMeasured") : t("outOf5", { value: num(m.value, 2) });
      case "unresolved":
        return m.count == null ? t("notMeasured") : `${num(m.count, 0)}` + (m.value != null ? ` (${formatPercent(m.value, i18n.language)})` : "");
    }
  };
}

/** Display name of a split group. */
export function useGroupLabel() {
  const { t } = useTranslation("dashboard");
  const { t: ts } = useTranslation("staff");
  return (split: string, key: string): string => {
    if (key === "all") return t("group.all");
    const k = groupLabelKey(split, key);
    if (k === null) return key;
    return k.startsWith("language.") ? ts(k, { defaultValue: key }) : t(k, { defaultValue: key });
  };
}
