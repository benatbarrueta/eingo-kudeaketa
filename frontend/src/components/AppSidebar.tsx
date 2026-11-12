import { CalendarDays, FileText, LayoutDashboard } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import type { Config } from "../types/calendar";
import { t } from "../lib/labels";

const navigationItems = [
  { path: "/", label: t.home, Icon: LayoutDashboard },
  { path: "/events", label: t.events, Icon: CalendarDays },
  { path: "/document", label: t.document, Icon: FileText },
];

export function AppSidebar({ source }: { source?: Config["source"] }) {
  return (
    <aside className="sidebar">
      <Link to="/" className="brand">
        <span className="brandIcon">
          <CalendarDays size={24} />
        </span>
        <span>
          EINGO Kudeaketa<small>{t.agenda}</small>
        </span>
      </Link>
      <div className="sideLabel">{t.workspace}</div>
      <nav aria-label={t.workspace}>
        {navigationItems.map(({ path, label, Icon }) => (
          <NavLink
            key={path}
            to={path}
            end
            className={({ isActive }) => (isActive ? "selected" : "")}
          >
            <Icon size={19} />
            {label}
          </NavLink>
        ))}
      </nav>
      {source && (
        <div className="source">
          <span>{t.source}</span>
          <strong>{source === "sheets" ? t.sheetsSource : source === "google" ? t.external : t.local}</strong>
        </div>
      )}
    </aside>
  );
}
