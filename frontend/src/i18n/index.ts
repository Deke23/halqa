import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { LANGUAGES, RTL_LANGUAGES, type Language } from "@/config";

import enCommon from "./locales/en/common.json";
import enPatient from "./locales/en/patient.json";
import enStaff from "./locales/en/staff.json";
import enDashboard from "./locales/en/dashboard.json";
import arCommon from "./locales/ar/common.json";
import arPatient from "./locales/ar/patient.json";
import arStaff from "./locales/ar/staff.json";
import arDashboard from "./locales/ar/dashboard.json";
import frCommon from "./locales/fr/common.json";
import frPatient from "./locales/fr/patient.json";
import frStaff from "./locales/fr/staff.json";
import frDashboard from "./locales/fr/dashboard.json";

export const NAMESPACES = ["common", "patient", "staff", "dashboard"] as const;
const STORAGE_KEY = "halqa.lang";

function readStoredLanguage(): Language {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v && (LANGUAGES as readonly string[]).includes(v)) return v as Language;
  } catch {
    /* storage may be blocked */
  }
  return "en";
}

/** Sets lang and dir on <html>. Called on init and on every language change. */
export function applyDocumentLanguage(lng: string) {
  const dir = (RTL_LANGUAGES as readonly string[]).includes(lng) ? "rtl" : "ltr";
  document.documentElement.lang = lng;
  document.documentElement.dir = dir;
}

export function setLanguage(lng: Language) {
  try {
    localStorage.setItem(STORAGE_KEY, lng);
  } catch {
    /* ignore */
  }
  void i18n.changeLanguage(lng);
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { common: enCommon, patient: enPatient, staff: enStaff, dashboard: enDashboard },
    ar: { common: arCommon, patient: arPatient, staff: arStaff, dashboard: arDashboard },
    fr: { common: frCommon, patient: frPatient, staff: frStaff, dashboard: frDashboard },
  },
  lng: readStoredLanguage(),
  fallbackLng: "en",
  supportedLngs: [...LANGUAGES],
  ns: [...NAMESPACES],
  defaultNS: "common",
  interpolation: { escapeValue: false },
  returnNull: false,
});

applyDocumentLanguage(i18n.language);
i18n.on("languageChanged", applyDocumentLanguage);

export default i18n;
