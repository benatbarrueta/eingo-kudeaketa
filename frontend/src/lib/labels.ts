import i18n from "i18next";
import { initReactI18next, useTranslation } from "react-i18next";
import eu from "./locales/eu.json";
import es from "./locales/es.json";

export const languageStorageKey = "eingo.language";
function initialLanguage() {
  try { return localStorage.getItem(languageStorageKey) === "es" ? "es" : "eu"; }
  catch { return "eu"; }
}
function applyLanguage(language: string) {
  document.documentElement.lang = language;
  document.title = language === "es" ? es.appName : eu.appName;
  try { localStorage.setItem(languageStorageKey, language); } catch { /* Language still works without storage. */ }
}
i18n.on("languageChanged", applyLanguage);
void i18n.use(initReactI18next).init({
  resources: { eu: { translation: eu }, es: { translation: es } },
  lng: initialLanguage(), fallbackLng: "eu", supportedLngs: ["eu", "es"],
  interpolation: { escapeValue: false }, initAsync: false,
});

type Labels = Omit<typeof eu, "months" | "weekdays">;
// API helpers resolve messages in the language selected when the request finishes.
export const t = new Proxy({} as Labels, {
  get: (_target, key: string) => i18n.t(key),
});
export function useLabels() {
  const { i18n } = useTranslation();
  const labels = i18n.resolvedLanguage === "es" ? es : eu;
  return { t: labels, months: labels.months, weekdays: labels.weekdays,
    language: i18n.resolvedLanguage === "es" ? "es" : "eu",
    changeLanguage: (language: string) => { if (language === "eu" || language === "es") void i18n.changeLanguage(language); },
    columnLabel: (column: string) => i18n.t("column_" + column, { defaultValue: column }),
    descriptionLabel: (value: string) => i18n.t("description_" + value, { defaultValue: value }),
    message: (value: string) => {
      const key = (Object.keys(eu) as (keyof typeof eu)[]).find(key => eu[key] === value || es[key] === value);
      return key ? i18n.t(key) : value;
    },
  };
}
export default i18n;
