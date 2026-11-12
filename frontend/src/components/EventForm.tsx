import { useEffect, useRef, useState, type FormEvent } from "react";
import "../styles/EventForm.css";
import { X } from "lucide-react";
import { createEvent, updateEvent, deleteEvent } from "../api/calendar";
import type { Config, EventRow, SaveResult, Table } from "../types/calendar";
import { useLabels } from "../lib/labels";

const descriptionOptions = ["ERROMERIA", "IBILTARIA"];
const otherDescription = "other";

function nativeValue(column: string, value: string) {
  if (column === "ORDUA" && !/^([01]\d|2[0-3]):[0-5]\d$/.test(value)) return "";
  if (column === "FAKTURAZIOA" && !/^-?\d+(\.\d+)?$/.test(value)) return "";
  return value;
}

export function EventForm({
  config,
  columns,
  target,
  initialDate,
  deleting,
  deleted,
  close,
  saved,
}: {
  config: Config;
  columns: string[];
  target?: EventRow;
  initialDate?: string;
  deleting: boolean;
  deleted: (table: Table) => void;
  close: () => void;
  saved: (result: SaveResult) => void;
}) {
  const { t, columnLabel, descriptionLabel, message } = useLabels();
  const [openedAt] = useState(() => new Date());
  const pad = (value: number) => String(value).padStart(2, "0");
  const firstDate = config.year + "-01-01";
  const lastDate = config.year + "-12-31";
  const today = `${openedAt.getFullYear()}-${pad(openedAt.getMonth() + 1)}-${pad(openedAt.getDate())}`;
  const defaultDate = today < firstDate ? firstDate : today > lastDate ? lastDate : today;
  const defaultTime = `${pad(openedAt.getHours())}:${pad(openedAt.getMinutes())}`;
  const initial = Object.fromEntries(columns.map((column, index) => [column, target?.values[index] ?? ""]));
  const initialDescription = initial.AZALPENA ?? "";
  const standardDescription = descriptionOptions.find(
    (option) => option === initialDescription.toUpperCase(),
  );
  const [description, setDescription] = useState(
    standardDescription ?? (initialDescription ? otherDescription : ""),
  );
  const extraColumns = columns.filter((column) => column !== "DATA" && column !== "HERRIA");
  const title = deleting ? t.deleteEvent : target ? t.editEvent : t.add;
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!dialog.current?.open) dialog.current?.showModal();
  }, []);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      if (deleting && target) {
        deleted(await deleteEvent(target.id, target.values));
        return;
      }
      const customDescription = String(data.get("customDescription") ?? "").trim();
      if (extraColumns.includes("AZALPENA") && description === otherDescription && !customDescription) {
        setError(t.descriptionRequired);
        return;
      }
      const fields = Object.fromEntries(
        extraColumns.flatMap((column) => {
          let value = String(data.get("field:" + column) ?? "");
          if (column === "AZALPENA") {
            value = description === otherDescription
              ? customDescription
              : description === standardDescription ? initialDescription : description;
          }
          if (target && !value && initial[column] && !nativeValue(column, initial[column])) {
            return [];
          }
          return target && value === initial[column] ? [] : [[column, value]];
        }),
      );
      const input = { date: String(data.get("date")), town: String(data.get("town")), fields };
      saved(target
        ? await updateEvent(target.id, target.values, input)
        : await createEvent(input));
    } catch (err) {
      setError(err instanceof Error ? err.message : t.failed);
    } finally {
      setBusy(false);
    }
  }
  return (
    <dialog
      ref={dialog}
      aria-labelledby="form-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) close();
      }}
    >
      <div className="panelHead">
        <h2 id="form-title">{title}</h2>
        <button
          className="iconButton"
          onClick={close}
          disabled={busy}
          aria-label={t.cancel}
        >
          <X size={19} />
        </button>
      </div>
      <p className="muted">{deleting ? `${t.deleteConfirm} ${initial.HERRIA} · ${target?.date}` : t.formHelp}</p>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          {!deleting && <>
          <label>
            {t.date}
            <input
              autoFocus
              name="date"
              type="date"
              defaultValue={target?.date ?? initialDate ?? defaultDate}
              min={firstDate}
              max={lastDate}
              required
            />
          </label>
          <label>
            {t.town}
            <input name="town" defaultValue={initial.HERRIA} maxLength={240} required />
          </label>
          {extraColumns.map((column) => {
            const fieldName = "field:" + column;
            const existing = initial[column];
            if (column === "AZALPENA") {
              return (
                <div className="descriptionFields" key={column}>
                  <label>
                    {columnLabel(column)}
                    <select value={description} onChange={(event) => setDescription(event.target.value)}>
                      <option value="">{t.chooseDescription}</option>
                      {descriptionOptions.map((option) => (
                        <option key={option} value={option}>{descriptionLabel(option)}</option>
                      ))}
                      <option value={otherDescription}>{t.otherDescription}</option>
                    </select>
                  </label>
                  {description === otherDescription && (
                    <label>
                      {t.customDescription}
                      <input
                        name="customDescription"
                        defaultValue={standardDescription ? "" : initialDescription}
                        maxLength={Math.max(240, initialDescription.length)}
                        required
                      />
                    </label>
                  )}
                </div>
              );
            }
            if (column === "ORDUA" || column === "FAKTURAZIOA") {
              const value = nativeValue(column, existing);
              return (
                <label key={column}>
                  {columnLabel(column)}
                  <input
                    name={fieldName}
                    type={column === "ORDUA" ? "time" : "number"}
                    step={column === "FAKTURAZIOA" ? "any" : undefined}
                    defaultValue={!target && column === "ORDUA" ? defaultTime : value}
                  />
                  {existing && !value && <small className="muted">{t.currentFieldValue} {existing}</small>}
                </label>
              );
            }
            return (
              <label key={column}>
                {columnLabel(column)}
                <textarea
                  name={fieldName}
                  defaultValue={existing}
                  rows={existing.includes("\n") ? 3 : 1}
                  maxLength={Math.max(240, existing.length)}
                />
              </label>
            );
          })}
          </>}

        </fieldset>
        {error && (
          <p className="error" role="alert">
            {message(error)}
          </p>
        )}
        <div className="formActions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={close}
          >
            {t.cancel}
          </button>
          <button className={deleting ? "primary danger" : "primary"} disabled={busy}>
            {busy ? t.saving : deleting ? t.deleteEvent : t.save}
          </button>
        </div>
      </form>
    </dialog>
  );
}
