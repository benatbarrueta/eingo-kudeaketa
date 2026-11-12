import { Pencil, Trash2 } from "lucide-react";
import type { EventRow } from "../types/calendar";
import { months, t } from "../lib/labels";
import { eventMonth } from "../lib/calendar";
import "../styles/EventList.css";

export function EventList({
  events,
  columns,
  highlight,
  onEdit,
  onDelete,
}: {
  events: EventRow[];
  columns: string[];
  highlight?: number;
  onEdit?: (event: EventRow) => void;
  onDelete?: (event: EventRow) => void;
}) {
  const town = columns.indexOf("HERRIA");
  return (
    <ul className="eventList">
      {events.map((e) => (
        <li key={e.id} className={e.id === highlight ? "highlight" : ""}>
          <div className="dateTile">
            <strong>{Number(e.date.slice(8))}</strong>
            <span>{months[eventMonth(e.date)].slice(0, 3)}</span>
          </div>
          <div>
            <strong>{e.values[town]}</strong>
            <div className="eventFields">
              {columns.flatMap((c, i) =>
                c !== "DATA" && i !== town
                  ? [
                      <span key={c}>
                        {c}: {e.values[i] || "—"}
                      </span>,
                    ]
                  : [],
              )}
            </div>
          </div>
          {onEdit && onDelete && (
            <div className="eventActions">
              <button
                type="button"
                className="secondary eventAction"
                aria-label={t.editEvent + " · " + e.values[town]}
                title={t.editEvent}
                onClick={() => onEdit(e)}
              >
                <Pencil size={24} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="secondary eventAction eventActionDelete"
                aria-label={t.deleteEvent + " · " + e.values[town]}
                title={t.deleteEvent}
                onClick={() => onDelete(e)}
              >
                <Trash2 size={24} aria-hidden="true" />
              </button>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
