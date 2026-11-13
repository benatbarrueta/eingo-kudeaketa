import { useState } from "react";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import type { Config, EventRow, Table } from "../types/calendar";
import { useLabels } from "../lib/labels";
import { eventMonth } from "../lib/calendar";
import "../styles/CalendarPage.css";

function localIso(day: Date) {
  return [day.getFullYear(), String(day.getMonth() + 1).padStart(2, "0"), String(day.getDate()).padStart(2, "0")].join("-");
}

export function CalendarPage({ events, table, config, onEdit, onAdd }: {
  events: EventRow[];
  table: Table;
  config: Config;
  onEdit: (event: EventRow) => void;
  onAdd: (date: string) => void;
}) {
  const { t, months, weekdays } = useLabels();
  const now = new Date();
  const [month, setMonth] = useState(() => config.year === now.getFullYear()
    ? now.getMonth() : events.length ? eventMonth(events[0].date) : 0);
  const offset = (new Date(config.year, month, 1).getDay() + 6) % 7;
  const days = Array.from({ length: 42 }, (_, index) => new Date(config.year, month, index - offset + 1));
  const today = localIso(now);
  const townIndex = table.columns.indexOf("HERRIA");
  const timeIndex = table.columns.indexOf("ORDUA");
  const monthEvents = events.filter((event) => eventMonth(event.date) === month);
  const eventsByDate = new Map<string, EventRow[]>();
  for (const event of monthEvents) {
    const dayEvents = eventsByDate.get(event.date) ?? [];
    dayEvents.push(event);
    eventsByDate.set(event.date, dayEvents);
  }

  return (
    <>
      <div className="panelHead calendarToolbar">
        <div><h1>{t.calendar}</h1><p className="muted">{t.calendarDescription}</p></div>
        <div className="calendarControls">
          <button className="secondary" disabled={month === 0} aria-label={t.previousMonth} onClick={() => setMonth(month - 1)}>
            <ChevronLeft size={18} aria-hidden="true" />
          </button>
          <label className="monthPicker">
            <span className="visuallyHidden">{t.chooseMonth}</span>
            <select value={month} onChange={(event) => setMonth(Number(event.target.value))}>
              {months.map((name, index) => <option key={name} value={index}>{name} {config.year}</option>)}
            </select>
          </label>
          <button className="secondary" disabled={month === 11} aria-label={t.nextMonth} onClick={() => setMonth(month + 1)}>
            <ChevronRight size={18} aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="calendarSummary" role="status">{months[month]} · {monthEvents.length} {t.count}</div>
      <div className="card calendarViewport" tabIndex={0} role="region" aria-label={t.calendar}>
        <div className="monthGrid">
          {weekdays.map((day) => <div className="weekday" key={day}>{day}</div>)}
          {days.map((day) => {
            const iso = localIso(day);
            const active = day.getMonth() === month && day.getFullYear() === config.year;
            const dayEvents = active ? eventsByDate.get(iso) ?? [] : [];
            return (
              <section key={iso} className={["calendarDay", !active ? "outsideMonth" : "", iso === today ? "isToday" : ""].join(" ")} aria-label={iso}>
                <div className="dayHeading">
                  <time dateTime={iso} aria-current={iso === today ? "date" : undefined}>{day.getDate()}</time>
                  {active && <button className="dayAdd" aria-label={t.add + " · " + iso} title={t.add} onClick={() => onAdd(iso)}><Plus size={15} aria-hidden="true" /></button>}
                </div>
                <div className="dayEvents">
                  {dayEvents.map((event) => (
                    <button className="calendarEvent" key={event.id} onClick={() => onEdit(event)}
                      title={t.editEvent + " · " + event.values[townIndex]}>
                      {timeIndex >= 0 && event.values[timeIndex] && <span>{event.values[timeIndex]}</span>}
                      <strong>{event.values[townIndex]}</strong>
                    </button>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </div>
      {!monthEvents.length && <p className="muted calendarEmpty">{t.noResults}</p>}
    </>
  );
}
