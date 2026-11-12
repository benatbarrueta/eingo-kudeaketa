import { ArrowRight, CalendarDays, Layers3, MapPin } from "lucide-react";
import type { Config, EventRow, Table } from "../types/calendar";
import { t } from "../lib/labels";
import { eventMonth } from "../lib/calendar";
import { EventList } from "../components/EventList";
import "../styles/DashboardPage.css";

export function DashboardPage({
  events,
  table,
  config,
  go,
}: {
  events: EventRow[];
  table: Table;
  config: Config;
  go: () => void;
}) {
  const town = table.columns.indexOf("HERRIA");
  const now = new Date();
  const today = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
  const upcoming = events.filter((e) => e.date >= today).slice(0, 5);
  const towns = [
    ...new Map(
      events.map((e) => [e.values[town].toLocaleLowerCase(), e.values[town]]),
    ).values(),
  ].sort((a, b) => a.localeCompare(b, "eu"));
  const stats = [
    { label: t.total, value: events.length, Icon: CalendarDays },
    { label: t.locations, value: towns.length, Icon: MapPin },
    {
      label: t.active,
      value: new Set(events.map((e) => eventMonth(e.date))).size,
      Icon: Layers3,
    },
  ];
  return (
    <>
      <div className="hero">
        <div className="eyebrow">
          {t.overview} <span>·</span> {config.year}
        </div>
        <h1>{table.title}</h1>
        <p>{t.intro}</p>
        <div className="heroArt" aria-hidden>
          <CalendarDays size={172} strokeWidth={0.65} />
        </div>
      </div>
      <div className="stats">
        {stats.map(({ label, value, Icon }) => (
          <div key={label} className="card stat">
            <span className="statIcon">
              <Icon size={20} />
            </span>
            <div>
              <div className="statValue">{value}</div>
              <span className="muted">{label}</span>
            </div>
          </div>
        ))}
      </div>
      <section className="card panel">
        <div className="panelHead">
          <h2>{t.upcoming}</h2>
          <button className="linkButton" onClick={go}>
            {t.all}
            <ArrowRight size={16} />
          </button>
        </div>
        {upcoming.length ? (
          <EventList events={upcoming} columns={table.columns} />
        ) : (
          <p className="muted">{t.emptyUpcoming}</p>
        )}
      </section>
      {!!towns.length && (
        <section className="card panel">
          <div className="panelHead">
            <h2>{t.locations}</h2>
          </div>
          <ul className="towns">
            {towns.map((town) => (
              <li key={town}>
                <MapPin size={13} aria-hidden />
                {town}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
