import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const en = {
  nav: {
    dashboard: "Dashboard",
    live: "Live",
    events: "Events",
    analytics: "Analytics",
    materials: "Materials",
    workers: "Workers",
    zones: "Zones",
    cameras: "Cameras",
    test: "Test",
    settings: "Settings",
  },
  app: "SiteGuard",
};

const ar = {
  nav: {
    dashboard: "لوحة",
    live: "مباشر",
    events: "أحداث",
    analytics: "تحليلات",
    materials: "مواد",
    workers: "عمال",
    zones: "مناطق",
    cameras: "كاميرات",
    test: "اختبار",
    settings: "إعدادات",
  },
  app: "سايت جارد",
};

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, ar: { translation: ar } },
  lng: localStorage.getItem("siteguard_lang") || "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setLanguage(lng: "en" | "ar"): void {
  localStorage.setItem("siteguard_lang", lng);
  void i18n.changeLanguage(lng);
  document.documentElement.lang = lng;
  document.documentElement.dir = lng === "ar" ? "rtl" : "ltr";
}

export default i18n;
