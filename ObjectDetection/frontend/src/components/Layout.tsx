import {
  Bell,
  Box,
  Camera,
  ChartColumn,
  Clapperboard,
  HardHat,
  LayoutDashboard,
  Radio,
  Settings,
  Shield,
  Users,
  Video,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { setLanguage } from "../i18n";
import { useLive } from "../store/live";
import { WsStatusIndicator } from "./WsStatusIndicator";

const links = [
  ["/", "dashboard", LayoutDashboard],
  ["/live", "live", Video],
  ["/events", "events", Bell],
  ["/analytics", "analytics", ChartColumn],
  ["/materials", "materials", Box],
  ["/workers", "workers", Users],
  ["/zones", "zones", Shield],
  ["/cameras", "cameras", Camera],
  ["/test", "test", Clapperboard],
  ["/settings", "settings", Settings],
] as const;

export function Layout({
  onLogout,
  leaveSample,
  mock,
}: {
  onLogout: () => void;
  leaveSample: () => void;
  mock: boolean;
}) {
  const { t, i18n } = useTranslation();
  const alerts = useLive((s) => s.events.filter((e) => e.status === "open").length);
  const toggleTheme = () => {
    document.documentElement.classList.toggle("dark");
    document.documentElement.classList.toggle("light");
  };
  return (
    <div className="grid min-h-full grid-cols-1 lg:grid-cols-[240px_1fr]">
      <aside className="border-b border-[var(--line)] p-4 lg:border-b-0 lg:border-r">
        <div className="mb-6 flex items-center gap-2">
          <HardHat className="text-safety" />
          <div>
            <div className="font-semibold">{t("app")}</div>
            <div className="text-xs text-[var(--muted)]">Offline control room</div>
          </div>
        </div>
        <nav className="flex flex-wrap gap-2 lg:flex-col">
          {links.map(([to, key, Icon]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-xl px-3 py-2 text-sm ${isActive ? "bg-safety/15 text-safety" : "text-[var(--muted)]"}`
              }
            >
              <Icon size={16} />
              {t(`nav.${key}`)}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div>
        <header className="flex items-center justify-between gap-3 border-b border-[var(--line)] px-4 py-3">
          <WsStatusIndicator />
          <div className="mono text-sm">{new Date().toLocaleTimeString()}</div>
          <div className="flex items-center gap-3 text-sm">
            <span className="inline-flex items-center gap-1" aria-label="Open alerts">
              <Radio size={16} /> {alerts}
            </span>
            <button type="button" onClick={() => setLanguage(i18n.language === "ar" ? "en" : "ar")}>
              {i18n.language === "ar" ? "EN" : "AR"}
            </button>
            <button type="button" onClick={toggleTheme}>
              Theme
            </button>
            <button type="button" onClick={onLogout}>
              {mock ? "Sign in" : "Sign out"}
            </button>
          </div>
        </header>
        <main className="p-4">
          <Outlet context={{ mock, leaveSample }} />
        </main>
      </div>
    </div>
  );
}
