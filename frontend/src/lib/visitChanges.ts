import type { Table } from "../types/calendar";

export type VisitChange = { kind: "added" | "removed" | "updated"; date: string; town: string; fields: { name: string; before: string; after: string }[] };

// Match exact rows first, then unique date/town pairs. Ambiguous events remain
// additions/removals rather than attributing an edit to the wrong event.
export function visitChanges(before: Table, after: Table): VisitChange[] {
  const old = before.rows.filter(r => r.kind === "event").slice();
  const next = after.rows.filter(r => r.kind === "event").slice();
  for (let i = old.length - 1; i >= 0; i--) {
    const j = next.findIndex(r => r.date === old[i].date && JSON.stringify(r.values) === JSON.stringify(old[i].values));
    if (j >= 0) { old.splice(i, 1); next.splice(j, 1); }
  }
  const changes: VisitChange[] = [];
  for (let i = old.length - 1; i >= 0; i--) {
    const row = old[i];
    const matches = next.filter(r => r.date === row.date && r.values[1] === row.values[1]);
    if (matches.length !== 1 || old.filter(r => r.date === row.date && r.values[1] === row.values[1]).length !== 1) continue;
    const updated = matches[0];
    changes.push({ kind: "updated", date: updated.date ?? "", town: updated.values[1], fields: after.columns.flatMap((name, index) => {
      const previous = before.columns.indexOf(name);
      const value = previous < 0 ? "" : row.values[previous] ?? "";
      const current = updated.values[index] ?? "";
      return value === current ? [] : [{ name, before: value, after: current }];
    }) });
    old.splice(i, 1); next.splice(next.indexOf(updated), 1);
  }
  for (const row of old) changes.push({ kind: "removed", date: row.date ?? "", town: row.values[1], fields: [] });
  for (const row of next) changes.push({ kind: "added", date: row.date ?? "", town: row.values[1], fields: [] });
  return changes.sort((a, b) => a.date.localeCompare(b.date));
}

export function visitKey(config: { source: string; year: number; documentUrl: string | null; spreadsheetUrl?: string | null }) {
  return "eingo:last-visit:v1:" + JSON.stringify([config.source, config.year, config.documentUrl, config.spreadsheetUrl]);
}

export function readVisit(key: string): Table | undefined {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(key) ?? "null");
    if (!saved || typeof saved !== "object") return;
    const table = saved as Table;
    if (!Array.isArray(table.columns) || !table.columns.every(c => typeof c === "string") || !Array.isArray(table.rows)) return;
    if (!table.rows.every(r => r && typeof r.kind === "string" && (r.date === null || typeof r.date === "string") && Array.isArray(r.values) && r.values.every(v => typeof v === "string"))) return;
    return table;
  } catch { return; }
}

export function saveVisit(key: string, table: Table): boolean {
  try { localStorage.setItem(key, JSON.stringify(table)); return true; } catch { return false; }
}
