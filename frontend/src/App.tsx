import { useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { CircleCheck } from "lucide-react";
import { VisitChanges } from "./components/VisitChanges";
import { AppHeader } from "./components/AppHeader";
import { EventForm } from "./components/EventForm";
import { useCalendar } from "./hooks/useCalendar";
import { DashboardPage } from "./pages/DashboardPage";
import { CalendarPage } from "./pages/CalendarPage";
import { SpreadsheetPage } from "./pages/SpreadsheetPage";
import { DocumentPage } from "./pages/DocumentPage";
import { EventsPage } from "./pages/EventsPage";
import { resetDemo, importDocument, synchronizeDocument } from "./api/calendar";
import type { EventRow, SaveResult, Table } from "./types/calendar";
import { useLabels } from "./lib/labels";
import "./styles/App.css";

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

function AppRoutes() {
  const { t, message } = useLabels();
  const navigate = useNavigate();
  const { changes, storageError, syncStatus, config, table, setTable, loading, error, refresh } = useCalendar();
  const [formOpen, setFormOpen] = useState(false);
  const [initialDate, setInitialDate] = useState<string>();
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

  function openForm(event?: EventRow, remove = false, date?: string) {
    setInitialDate(date);
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
    setResetting(true);
    setActionError("");
    setNotice("");
    try {
      if (importing) await importDocument();
      else await synchronizeDocument();
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
      <div className="workspace">
        <AppHeader
          config={config}
          connected={!!table}
          canAdd={!!table && !loading && !resetting}
          onAdd={() => openForm()}
        />
        <main>
          {storageError && <p className="error" role="status">{t.visitStorageError}</p>}
          <VisitChanges changes={changes} />
          {syncStatus?.enabled && (
            <p className={syncStatus.error ? "error" : "muted"} role="status">
              {syncStatus.error ? t.syncConflict : t.autoSync}
            </p>
          )}
          {notice && (
            <div className="notice" role="status">
              <CircleCheck size={18} />
              {message(notice)}
            </div>
          )}
          {actionError && (
            <p className="error" role="alert">
              {message(actionError)}
            </p>
          )}
          {loading && <p role="status">{t.loading}</p>}
          {!loading && error && (
            <div className="card panel">
              <p className="error" role="alert">
                {message(error)}
              </p>
              <button className="secondary" onClick={() => void refresh()}>
                {t.retry}
              </button>
            </div>
          )}
          {!loading && !error && config && table && (
            <Routes>
              <Route path="calendar" element={
                <CalendarPage events={events} table={table} config={config}
                  onEdit={openForm} onAdd={(date) => openForm(undefined, false, date)} />
              } />
              <Route path="spreadsheet" element={
                <SpreadsheetPage table={table} config={config} highlight={highlight}
                  busy={resetting} onImport={() => void runSheetsAction(true)}
                  onSynchronize={() => void runSheetsAction(false)} />
              } />
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
                    busy={resetting}
                    onSynchronize={() => void runSheetsAction(false)}
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
          initialDate={initialDate}
          deleting={deleting}
          deleted={onDeleted}
          close={() => setFormOpen(false)}
          saved={onSaved}
        />
      )}
    </div>
  );
}
