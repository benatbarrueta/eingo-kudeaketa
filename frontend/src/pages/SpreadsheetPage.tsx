import { FilePageHeader } from "../components/FilePageHeader";
import type { Config, Table } from "../types/calendar";
import { useLabels } from "../lib/labels";
import "../styles/SpreadsheetPage.css";

export function SpreadsheetPage({ table, config, highlight, busy, onImport, onSynchronize }: {
  table: Table;
  config: Config;
  highlight?: number;
  busy: boolean;
  onImport: () => void;
  onSynchronize: () => void;
}) {
  const { t, columnLabel } = useLabels();
  const rows = table.rows.map((row, id) => ({ ...row, id })).filter((row) => row.kind === "event");

  return (
    <>
      <FilePageHeader
        title={t.spreadsheet}
        description={t.spreadsheetDescription}
        url={config.spreadsheetUrl}
        openLabel={t.openSpreadsheet}
        canSynchronize={config.source === "sheets"}
        busy={busy}
        onSynchronize={onSynchronize}
      />
      {config.source === "sheets" && rows.length === 0 && (
        <button className="secondary" disabled={busy} onClick={onImport}>{t.importDocument}</button>
      )}
      {config.source !== "sheets" && <p className="muted">{t.spreadsheetDemo}</p>}
      <div className="card spreadsheetView" role="region" aria-label={t.spreadsheet} tabIndex={0}>
        <table className="spreadsheetTable">
          <caption>{table.title} · {config.year} · {rows.length} {t.count}</caption>
          <thead>
            <tr>
              <th scope="col" className="rowNumber">#</th>
              {table.columns.map((column) => <th scope="col" key={column}>{columnLabel(column)}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id} className={row.id === highlight ? "highlight" : ""}>
                <th scope="row" className="rowNumber">{index + 2}</th>
                {row.values.map((value, column) => <td key={column}>{value || "—"}</td>)}
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={table.columns.length + 1}>{t.noResults}</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
