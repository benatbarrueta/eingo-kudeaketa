import { Search } from "lucide-react";
import type { EventRow, Table } from "../types/calendar";
import { months, t } from "../lib/labels";
import { eventMonth } from "../lib/calendar";
import { EventList } from "../components/EventList";
import { useState } from "react";
import "../styles/EventsPage.css";

export function EventsPage({
  events,
  table,
  highlight,
  onEdit,
  onDelete,
}: {
  events: EventRow[];
  table: Table;
  highlight?: number;
  onEdit?: (event: EventRow) => void;
  onDelete?: (event: EventRow) => void;
}) {
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const town = table.columns.indexOf("HERRIA");
  const normalized = (s: string) =>
    s
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "")
      .toLocaleLowerCase();
  const results = events.filter(
    (e) =>
      (filter === "" || eventMonth(e.date) === Number(filter)) &&
      normalized(e.values[town]).includes(normalized(search.trim())),
  );
  return (
    <>
      <h1>{t.events}</h1>
      <div className="filters">
        <label className="search">
          <Search size={18} />
          <input
            aria-label={t.search}
            placeholder={t.search}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label={t.allMonths}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="">{t.allMonths}</option>
          {months.map((m, i) => (
            <option key={m} value={i}>
              {m}
            </option>
          ))}
        </select>
      </div>
      {!results.length && <p className="card panel muted">{t.noResults}</p>}
      {months.map((m, i) => {
        const rows = results.filter((e) => eventMonth(e.date) === i);
        return rows.length ? (
          <section className="card panel month" key={m}>
            <div className="panelHead">
              <h2>{m}</h2>
              <span className="badge">
                {rows.length} {t.count}
              </span>
            </div>
            <EventList
              events={rows}
              columns={table.columns}
              highlight={highlight}
              onEdit={onEdit}
              onDelete={onDelete}
            />
          </section>
        ) : null;
      })}
    </>
  );
}
