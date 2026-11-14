"""Preview field conflicts and require an unchanged snapshot before resolving them."""
from collections import Counter
from dataclasses import dataclass
import hashlib
import json

from app.models.calendar import CalendarError
from app.models.database import COLUMNS


@dataclass
class ConflictPreview:
    public: dict
    target: list
    current: list
    revision: str
    document: object
    sheets: list
    docs: list


def preview(engine):
    source, document, sheets, docs = engine._read()
    calendar = engine.database.read()
    current = engine._rows(calendar, 9)
    config, states, operation = engine.database.synchronization()
    base = [state.values for state in states]
    public = {"token": "", "fields": [], "canResolve": False, "reason": None}
    result = ConflictPreview(public, [], current, calendar.revision, document, sheets, docs)
    if operation:
        public["reason"] = "pending_operation"
        return result
    if not config.initialized:
        public["reason"] = "initial_mismatch"
        return result
    if (len({len(rows) for rows in (base, current, sheets, docs)}) != 1
            or [row.event_id for row in calendar.rows if row.kind == "event"] != [state.event_id for state in states]
            or any(any(count > 1 for count in Counter(tuple(row[:7]) for row in rows).values())
                   for rows in (base, current, sheets, docs))
            or any(row[:2] != original[:2] for rows in (current, sheets, docs)
                   for original, row in zip(base, rows))):
        # Row additions, deletions and identity changes need a separate review flow.
        public["reason"] = "ambiguous_structure"
        return result
    snapshot = {"base": base, "database": current, "sheets": sheets, "docs": docs,
                "databaseRevision": calendar.revision, "sheetsRevision": source.revision,
                "docsRevision": document.revision,
                "eventIds": [state.event_id for state in states]}
    public["token"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    events = calendar.events()
    for index, original in enumerate(base):
        target = []
        for column, old in enumerate(original):
            candidates = {"sheets": sheets[index][column]}
            if column < 7:
                candidates["docs"] = docs[index][column]
            candidates["database"] = current[index][column]
            changed = {value for value in candidates.values() if value != old}
            if len(changed) <= 1:
                target.append(next(iter(changed)) if changed else old)
                continue
            options = []
            for origin, value in candidates.items():
                if value != old and not any(option["value"] == value for option in options):
                    options.append({"source": origin, "value": value})
            public["fields"].append({"key": f"{states[index].event_id}:{COLUMNS[column]}",
                "date": events[index]["date"].isoformat(), "town": current[index][1],
                "column": COLUMNS[column], "options": options})
            target.append(old)  # Filled from the explicit selection before writing.
        result.target.append(target)
    public["canResolve"] = bool(public["fields"])
    return result


def resolve(engine, request):
    current = preview(engine)
    if current.public["token"] != request.token:
        raise CalendarError("conflict_changed")
    if not current.public["canResolve"]:
        raise CalendarError("conflict_not_resolvable")
    fields = {field["key"]: field for field in current.public["fields"]}
    if request.choices.keys() != fields.keys():
        raise CalendarError("validation_error", 422)
    _, states, operation = engine.database.synchronization()
    if operation:
        raise CalendarError("conflict_changed")
    positions = {state.event_id: index for index, state in enumerate(states)}
    for key, origin in request.choices.items():
        option = next((option for option in fields[key]["options"] if option["source"] == origin), None)
        if option is None:
            raise CalendarError("validation_error", 422)
        event_id, column = key.split(":")
        current.target[positions[event_id]][COLUMNS.index(column)] = option["value"]
    engine._validate(current.target, current.current, current.document)
    engine.database.checkpoint({"target": current.target, "database": current.current,
        "sheets": current.sheets, "docs": current.docs, "resolution": request.choices},
        expected_revision=current.revision)
    # The existing engine rechecks every source, checkpoints writes and verifies the result.
    engine.run()
