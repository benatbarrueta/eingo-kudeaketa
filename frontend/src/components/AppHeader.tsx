import { Plus } from "lucide-react";
import type { Config } from "../types/calendar";
import { t } from "../lib/labels";
import "../styles/AppHeader.css";

interface AppHeaderProps {
  config?: Config;
  connected: boolean;
  canAdd: boolean;
  onAdd: () => void;
}

export function AppHeader({
  config,
  connected,
  canAdd,
  onAdd,
}: AppHeaderProps) {
  const status =
    config?.source === "mock"
      ? t.demo
      : connected
        ? t.connected
        : t.disconnected;

  return (
    <header className="app-header">
      <span className="headerName">{t.agenda}</span>
      <div className="headerActions">
        {config && (
          <>
            <span
              className={connected ? "connection online" : "connection offline"}
            >
              <i />
              {status}
            </span>
            <span className="year">{config.year}</span>
          </>
        )}
        <button className="primary" disabled={!canAdd} onClick={onAdd}>
          <Plus size={19} />
          {t.add}
        </button>
      </div>
    </header>
  );
}
