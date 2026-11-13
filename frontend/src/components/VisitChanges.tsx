import { ArrowRight, ChevronDown, History, Pencil, Plus, Minus } from "lucide-react";
import type { VisitChange } from "../lib/visitChanges";
import { useLabels } from "../lib/labels";
import "../styles/VisitChanges.css";

export function VisitChanges({ changes }: { changes: VisitChange[] }) {
  const { t, columnLabel } = useLabels();
  if (!changes.length) return null;
  return (
    <details className="visitChanges" open>
      <summary className="visitChangesHeader">
        <span className="visitChangesIcon"><History size={19} aria-hidden="true" /></span>
        <span className="visitChangesHeading">{t.visitChanges}<span className="visitChangesSubtitle">{t.visitChangesSubtitle}</span></span>
        <span className="visitChangesCount">{changes.length}</span>
        <ChevronDown size={18} className="visitChangesChevron" aria-hidden="true" />
      </summary>
      <ul className="visitChangesList">
        {changes.map((change, index) => {
          const Icon = change.kind === "updated" ? Pencil : change.kind === "added" ? Plus : Minus;
          const [year, month, day] = change.date.split("-");
          return (
            <li className="visitChange" key={index}>
              <div className="visitChangeEvent">
                <span className={`visitChangeKind ${change.kind}`}><Icon size={13} aria-hidden="true" />{t[change.kind]}</span>
                <strong>{change.town}</strong>
                <time dateTime={change.date}>{day}/{month}/{year}</time>
              </div>
              {change.fields.length > 0 && <ul className="visitChangeFields">
                {change.fields.map(field => <li key={field.name}>
                  <span className="visitChangeFieldName">{columnLabel(field.name)}</span>
                  <span className="visitChangeBefore">{field.before || "—"}</span>
                  <ArrowRight size={14} aria-label={t.changedTo} />
                  <span className="visitChangeAfter">{field.after || "—"}</span>
                </li>)}
              </ul>}
            </li>
          );
        })}
      </ul>
    </details>
  );
}
