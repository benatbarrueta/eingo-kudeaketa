import { useEffect, useState } from "react";
import { getDocumentPreview } from "../api/calendar";
import { ExternalLink } from "lucide-react";
import type { Config, Table } from "../types/calendar";
import { t } from "../lib/labels";
import "../styles/DocumentPage.css";

export function DocumentPage({
  table: sourceTable,
  config,
  highlight,
  reset,
}: {
  table: Table;
  config: Config;
  highlight?: number;
  reset: () => void;
}) {
  const [document, setDocument] = useState<Table>();
  const [error, setError] = useState("");
  useEffect(() => {
    if (config.source !== "sheets") return;
    let active = true;
    getDocumentPreview().then((result) => {
      if (active) setDocument(result);
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : t.failed);
    });
    return () => { active = false; };
  }, [config.source, sourceTable]);
  const table = config.source === "sheets" ? document : sourceTable;
  if (error) return <p role="alert" className="error">{error}</p>;
  if (!table) return <p role="status">{t.loading}</p>;
  return (
    <>
      <div className="panelHead documentHead">
        <div>
          <h1>{t.document}</h1>
          <p className="muted">{t.preview}</p>
        </div>
        {config.documentUrl ? (
          <a
            className="secondary"
            href={config.documentUrl}
            target="_blank"
            rel="noreferrer"
          >
            {t.open}
            <ExternalLink size={16} />
          </a>
        ) : (
          <button className="secondary" onClick={reset}>
            {t.reset}
          </button>
        )}
      </div>
      {table.rows.some((r) => r.kind === "unknown") && (
        <p className="error" role="status">
          {t.unsafe}
        </p>
      )}
      <div
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
                  {c}
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
      </div>
    </>
  );
}
