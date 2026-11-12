import { CalendarDays, CalendarRange, FileSpreadsheet, FileText, LayoutDashboard, List, Plus } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import type { Config } from "../types/calendar";
import { useTheme } from "../hooks/useTheme";
import { t } from "../lib/labels";
import "../styles/AppHeader.css";

const navigationItems = [
  { path: "/", label: t.home, Icon: LayoutDashboard },
  { path: "/events", label: t.events, Icon: List },
  { path: "/calendar", label: t.calendar, Icon: CalendarDays },
  { path: "/spreadsheet", label: t.spreadsheet, Icon: FileSpreadsheet },
  { path: "/document", label: t.document, Icon: FileText },
];

interface AppHeaderProps {
  config?: Config;
  connected: boolean;
  canAdd: boolean;
  onAdd: () => void;
}

export function AppHeader({ config, connected, canAdd, onAdd }: AppHeaderProps) {
  useTheme();
  const status = config?.source === "mock" ? t.demo
    : !connected ? t.disconnected
    : config?.source === "sheets" ? t.sheetsConnected : t.connected;

  return (
    <header className="app-header">
      <div className="headerTop">
        <Link to="/" className="brand">
          <span className="brandIcon"><CalendarRange size={24} aria-hidden="true" /></span>
          <span>EINGO Kudeaketa<small>{t.agenda}</small></span>
        </Link>
        <div className="headerActions">
          {config && (
            <>
              <span className={connected ? "connection online" : "connection offline"}>
                <i aria-hidden="true" />{status}
              </span>
              <span className="year">{config.year}</span>
            </>
          )}
          <button className="primary" disabled={!canAdd} onClick={onAdd}>
            <Plus size={19} aria-hidden="true" />{t.add}
          </button>
        </div>
      </div>
      <nav className="headerNavigation" aria-label={t.workspace}>
        {navigationItems.map(({ path, label, Icon }) => (
          <NavLink key={path} to={path} end className={({ isActive }) => isActive ? "navLink selected" : "navLink"}>
            <Icon size={18} aria-hidden="true" />{label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
