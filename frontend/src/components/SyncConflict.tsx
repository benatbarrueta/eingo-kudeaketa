import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowRight, FileSpreadsheet, FileText, CalendarDays, RefreshCw } from "lucide-react";
import { getSyncConflict, resolveSyncConflict, type ConflictPreview, type ConflictSource } from "../api/calendar";
import { useLabels } from "../lib/labels";
import "../styles/SyncConflict.css";

export function ConflictChoices({ preview, choices, busy, onChoose }: {
  preview: ConflictPreview;
  choices: Record<string, ConflictSource>;
  busy: boolean;
  onChoose: (key: string, source: ConflictSource) => void;
}) {
  const { t, columnLabel, language } = useLabels();
  const sources = { sheets: "Google Sheets", docs: "Google Docs", database: t.conflictAgenda };
  const icons = { sheets: FileSpreadsheet, docs: FileText, database: CalendarDays };
  const dateFormat = new Intl.DateTimeFormat(language, { day: "numeric", month: "short", year: "numeric" });
  return <div className="syncConflictFields">
    {preview.fields.map((field) => <fieldset key={field.key} disabled={busy}>
      <legend><span className="syncConflictEvent"><span><strong>{field.town}</strong>
        <time dateTime={field.date}>{dateFormat.format(new Date(field.date + "T12:00:00"))}</time></span>
        <span className="syncConflictColumn">{columnLabel(field.column)}</span></span></legend>
      <div className="syncConflictOptions">
        {field.options.map((option) => {
          const Icon = icons[option.source];
          const selected = choices[field.key] === option.source;
          return <label key={option.source} className={`syncConflictOption ${selected ? "isSelected" : ""}`}>
          <input type="radio" name={field.key} value={option.source}
            checked={selected}
            onChange={() => onChoose(field.key, option.source)} />
          <span className={`syncConflictSource source-${option.source}`}><Icon size={17} aria-hidden="true" />{sources[option.source]}</span>
          <strong className="syncConflictValue">{option.value || t.conflictEmpty}</strong>
          <span className="syncConflictSelection">{selected ? t.conflictSelected : t.conflictChoose}</span>
        </label>;
        })}
      </div>
    </fieldset>)}
  </div>;
}

export function SyncConflict({ onResolved }: { onResolved: () => Promise<void> }) {
  const { t, message } = useLabels();
  const [preview, setPreview] = useState<ConflictPreview>();
  const [choices, setChoices] = useState<Record<string, ConflictSource>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const active = useRef(true);
  const submitting = useRef(false);
  const review = useCallback(async () => {
    setLoading(true);
    setError("");
    setChoices({});
    try {
      const result = await getSyncConflict();
      if (active.current) setPreview(result);
    } catch (cause) {
      if (active.current) {
        setPreview(undefined);
        setError(cause instanceof Error ? cause.message : "");
      }
    } finally {
      if (active.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    active.current = true;
    void review();
    return () => { active.current = false; };
  }, [review]);
  async function apply() {
    if (!preview || submitting.current || !preview.canResolve ||
        !preview.fields.every(field => choices[field.key])) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await resolveSyncConflict(preview.token, choices);
      await onResolved();
    } catch (cause) {
      if (active.current) {
        setChoices({});
        setPreview(undefined);
        setError(cause instanceof Error ? cause.message : "");
      }
    } finally {
      submitting.current = false;
      if (active.current) setBusy(false);
    }
  }
  const complete = !!preview?.canResolve && preview.fields.every(field => !!choices[field.key]);
  return <section className="card panel syncConflict" aria-labelledby="sync-conflict-title" aria-busy={loading || busy}>
    <div className="syncConflictHeader">
      <span className="syncConflictIcon"><AlertTriangle size={20} aria-hidden="true" /></span>
      <div><span className="syncConflictEyebrow">{t.conflictPaused}</span>
        <h2 id="sync-conflict-title">{t.conflictTitle}</h2></div>
    </div>
    <p className="syncConflictHelp">{t.conflictHelp}</p>
    {loading && <p role="status">{t.loading}</p>}
    {error && <p className="error" role="alert">{message(error)}</p>}
    {!loading && preview?.canResolve && <ConflictChoices preview={preview} choices={choices} busy={busy}
      onChoose={(key, source) => setChoices(current => ({ ...current, [key]: source }))} />}
    {!loading && preview && !preview.canResolve && <p role="status">
      {preview.reason === "pending_operation" ? t.conflictPending
        : preview.reason ? t.conflictStructural : t.conflictNone}
    </p>}
    <div className="syncConflictActions">
      <button className="linkButton syncConflictRefresh" disabled={busy || loading} onClick={() => void review()}>
        <RefreshCw size={15} aria-hidden="true" />{t.conflictReview}</button>
      <div className="syncConflictSubmit">
      {preview?.canResolve && <span className="syncConflictFootnote">{t.conflictApplyHelp}</span>}
      {preview?.canResolve && <button className="primary" disabled={busy || loading || !complete}
        onClick={() => void apply()}>{busy ? t.saving : t.conflictApply}<ArrowRight size={16} aria-hidden="true" /></button>}
      {preview && !preview.canResolve && !preview.reason &&
        <button className="primary" disabled={busy || loading} onClick={() => void onResolved()}>{t.retry}</button>}
      {preview?.reason === "pending_operation" &&
        <button className="primary" disabled={busy || loading} onClick={() => void onResolved()}>{t.synchronizeFiles}</button>}
      </div>
    </div>
  </section>;
}
