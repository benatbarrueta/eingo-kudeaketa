import { useEffect, useState } from "react";
import { getDocumentPreview } from "../api/calendar";
import { FilePageHeader } from "../components/FilePageHeader";
import type { Config, Table } from "../types/calendar";
import { useLabels } from "../lib/labels";
import "../styles/DocumentPage.css";

export function DocumentPage({
  table: sourceTable,
  config,
  highlight,
  reset,
  busy,
  onSynchronize,
}: {
  table: Table;
  config: Config;
  highlight?: number;
  reset: () => void;
  busy: boolean;
  onSynchronize: () => void;
}) {
  const { t, columnLabel, message } = useLabels();
  const [document, setDocument] = useState<Table>();
  const [error, setError] = useState("");
  useEffect(() => {
    if (config.source !== "sheets" && config.source !== "database") return;
    let active = true;
    getDocumentPreview().then((result) => {
      if (active) setDocument(result);
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : t.failed);
    });
    return () => { active = false; };
  }, [config.source, sourceTable]);
  const table = config.source === "sheets" || config.source === "database" ? document : sourceTable;
  return (
    <>
      <FilePageHeader
        title={t.document}
        description={t.preview}
        url={config.documentUrl}
        openLabel={t.open}
        canSynchronize={config.source === "sheets" || !!config.googleSync}
        busy={busy}
        onSynchronize={onSynchronize}
      />
      {config.source === "mock" && (
        <button className="secondary" disabled={busy} onClick={reset}>{t.reset}</button>
      )}
      {error && <p role="alert" className="error">{message(error)}</p>}
      {!table && !error && <p role="status">{t.loading}</p>}
      {table?.rows.some((r) => r.kind === "unknown") && (
        <p className="error" role="status">
          {t.unsafe}
        </p>
      )}
      {table && <div
        className="card sheet"
        tabIndex={0}
        role="region"
        aria-label={t.document}
      >
        <table>
          <thead>
            <tr>
              {table.columns.map((c) => (
                <th key={c} scope="col">
                  {columnLabel(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((r, i) =>
              i === 0 ? null : (
                <tr
                  key={i}
                  className={r.kind + (i === highlight ? " highlight" : "")}
                >
                  {r.values.map((v, j) => (
                    <td key={j} colSpan={r.spans?.[j] || 1}>
                      {v || "\u00a0"}
                    </td>
                  ))}
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>}
    </>
  );
}
