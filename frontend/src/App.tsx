import { useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { CircleCheck } from "lucide-react";
import { AppHeader } from "./components/AppHeader";
import { AppSidebar } from "./components/AppSidebar";
import { EventForm } from "./components/EventForm";
import { useCalendar } from "./hooks/useCalendar";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentPage } from "./pages/DocumentPage";
import { EventsPage } from "./pages/EventsPage";
import { resetDemo, importDocument, synchronizeDocument } from "./api/calendar";
import type { EventRow, SaveResult, Table } from "./types/calendar";
import { t } from "./lib/labels";
import "./styles/App.css";

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

function AppRoutes() {
  const navigate = useNavigate();
  const { syncStatus, config, table, setTable, loading, error, refresh } = useCalendar();
  const [formOpen, setFormOpen] = useState(false);
  const [target, setTarget] = useState<EventRow>();
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [highlight, setHighlight] = useState<number>();
  const [resetting, setResetting] = useState(false);

  const events: EventRow[] =
    table?.rows.flatMap((row, id) => {
      if (row.kind !== "event" || !row.date) return [];
      return [{ id, date: row.date, values: row.values }];
    }) ?? [];
  events.sort((a, b) => a.date.localeCompare(b.date));

  function openForm(event?: EventRow, remove = false) {
    setTarget(event);
    setDeleting(remove);
    setNotice("");
    setActionError("");
    setFormOpen(true);
  }

  function onSaved(result: SaveResult) {
    setTable(result.table);
    setFormOpen(false);
    setHighlight(result.event.id);
    setNotice(target ? t.edited : result.created ? t.saved : t.existing);
    navigate("/events");
  }

  function onDeleted(updated: Table) {
    setTable(updated);
    setFormOpen(false);
    setHighlight(undefined);
    setNotice(t.deleted);
  }

  async function runSheetsAction(importing: boolean) {
    if (resetting) return;
    if (importing && !window.confirm(t.importConfirm)) return;
    const localWrites = import.meta.env.DEV &&
      import.meta.env.VITE_LOCAL_WRITES === true &&
      location.hostname === "127.0.0.1" && !import.meta.env.VITE_API_URL;
    const token = localWrites ? "" : window.prompt(t.token);
    if (token === null) return;
    setResetting(true);
    setActionError("");
    setNotice("");
    try {
      if (importing) await importDocument(token);
      else await synchronizeDocument(token);
      await refresh();
      setNotice(importing ? t.importDone : t.syncDone);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : t.failed);
    } finally {
      setResetting(false);
    }
  }

  async function onReset() {
    if (resetting) return;
    setResetting(true);
    setActionError("");
    setNotice("");
    try {
      await resetDemo();
      setHighlight(undefined);
      await refresh();
      setNotice(t.resetDone);
    } catch {
      setActionError(t.failed);
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="layout">
      <AppSidebar source={config?.source} />
      <div className="workspace">
        <AppHeader
          config={config}
          connected={!!table}
          canAdd={!!table && !loading && !resetting}
          onAdd={() => openForm()}
        />
        <main>
          {config?.source === "sheets" && (
            <div className="panelHead">
              {config.spreadsheetUrl && <a className="secondary" href={config.spreadsheetUrl} target="_blank" rel="noreferrer">Google Sheets ↗</a>}
              <button className="secondary" disabled={resetting || loading} onClick={() => void runSheetsAction(true)}>{t.importDocument}</button>
              <button className="secondary" disabled={resetting || loading} onClick={() => void runSheetsAction(false)}>{t.synchronize}</button>
            </div>
          )}
          {syncStatus?.enabled && (
            <p className={syncStatus.error ? "error" : "muted"} role="status">
              {syncStatus.error ? t.syncConflict : t.autoSync}
            </p>
          )}
          {notice && (
            <div className="notice" role="status">
              <CircleCheck size={18} />
              {notice}
            </div>
          )}
          {actionError && (
            <p className="error" role="alert">
              {actionError}
            </p>
          )}
          {loading && <p role="status">{t.loading}</p>}
          {!loading && error && (
            <div className="card panel">
              <p className="error" role="alert">
                {error}
              </p>
              <button className="secondary" onClick={() => void refresh()}>
                {t.retry}
              </button>
            </div>
          )}
          {!loading && !error && config && table && (
            <Routes>
              <Route
                index
                element={
                  <DashboardPage
                    events={events}
                    table={table}
                    config={config}
                    go={() => navigate("/events")}
                  />
                }
              />
              <Route
                path="events"
                element={
                  <EventsPage
                    key={highlight ?? "events"}
                    events={events}
                    table={table}
                    highlight={highlight}
                    onEdit={openForm}
                    onDelete={(event) => openForm(event, true)}
                  />
                }
              />
              <Route
                path="document"
                element={
                  <DocumentPage
                    table={table}
                    config={config}
                    highlight={highlight}
                    reset={() => void onReset()}
                  />
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          )}
        </main>
      </div>
      {formOpen && config && table && (
        <EventForm
          config={config}
          columns={table.columns}
          target={target}
          deleting={deleting}
          deleted={onDeleted}
          close={() => setFormOpen(false)}
          saved={onSaved}
        />
      )}
    </div>
  );
}
