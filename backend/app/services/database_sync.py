"""Reconcile SQLite, Sheets and Docs with a durable plan and verified checkpoints."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json

from app.models.calendar import CalendarError
from app.services.bidirectional_sync import BidirectionalSync, align, merge
from app.utils.basque_dates import MONTHS, parse


class DatabaseSync(BidirectionalSync):
    def __init__(self, repository, database, path, year, identity):
        super().__init__(repository, path, year, identity)
        self.database = database

    def _database_rows(self):
        return self._rows(self.database.read(), 9)

    def _validate(self, target, current, document):
        # Never write Google before checking whether local identities can be retained.
        if any(count > 1 for count in Counter(tuple(row[:7]) for row in target).values()):
            raise CalendarError("sync_ambiguous_events")
        align(current, target, width=9)
        headings = {MONTHS.index(row.values[0].upper()) + 1
                    for row in document.rows if row.kind == "separator" and len(row.values) == 1
                    and row.values[0].upper() in MONTHS}
        months = headings | {event["date"].month for event in document.events()}
        for row in target:
            self.database._validate(row)
            if parse(row[0], self.year).month not in months:
                raise CalendarError("month_without_block")

    def validate_change(self, calendar, target):
        document = self.repository.document.read()
        if any(row.kind == "unknown" for row in document.rows):
            raise CalendarError("unsafe_structure")
        self._validate(target, self._rows(calendar, 9), document)

    def run(self):
        snapshots = {}
        try:
            source, document, sheets, docs = self._read()
            current = self._database_rows()
            config, states, operation = self.database.synchronization()
            base = [state.values for state in states]
            snapshots = {"base": base, "database": current, "sheets": sheets, "docs": docs}
            if operation:
                plan = operation.payload
                if current != plan["database"]:
                    raise CalendarError("sync_conflict")
            else:
                if not config.initialized:
                    if current:
                        # Connecting an already populated local agenda requires explicit agreement.
                        if current != sheets or docs != [row[:7] for row in current]:
                            raise CalendarError("sync_initial_mismatch")
                    if self.path.exists():
                        legacy = json.loads(self.path.read_text())
                        if legacy.get("identity") != self.identity:
                            raise CalendarError("sync_state_mismatch")
                        if "target" in legacy:
                            raise CalendarError("manual_review")
                        target = merge(legacy["base"], sheets, docs)
                    elif docs != [row[:7] for row in sheets]:
                        raise CalendarError("sync_initial_mismatch")
                    else:
                        target = sheets
                else:
                    remote = merge(base, sheets, docs)
                    target = merge(base, current, remote, width=9)
                target = sorted(target, key=lambda row: parse(row[0], self.year))
                self._validate(target, current, document)
                plan = {"target": target, "database": current, "sheets": sheets, "docs": docs}
                if current != target or sheets != target or docs != [row[:7] for row in target]:
                    self.database.checkpoint(plan)
            for _ in range(1000):
                source, document, sheets, docs = self._read()
                if self._database_rows() != plan["database"]:
                    raise CalendarError("sync_conflict")
                # A crash after a write but before its acknowledgement is recoverable
                # only if the subsequent read exactly matches the saved intention.
                if "next" in plan:
                    intended = plan["next"]
                    if sheets == intended["sheets"] and docs == intended["docs"]:
                        plan.update(intended)
                        del plan["next"]
                        self.database.checkpoint(plan)
                    elif sheets == plan["sheets"] and docs == plan["docs"]:
                        del plan["next"]
                        self.database.checkpoint(plan)
                    else:
                        raise CalendarError("sync_conflict")
                if sheets != plan["sheets"] or docs != plan["docs"]:
                    raise CalendarError("sync_conflict")
                target = plan["target"]
                if sheets == target and docs == [row[:7] for row in target]:
                    self.database.accept(target, plan["database"],
                        [event["id"] for event in source.events()],
                        [event["id"] for event in document.events()],
                        origin="import" if not config.initialized else "reconciliation")
                    self.repository.sync_pending = False
                    self.last_success = datetime.now(timezone.utc).isoformat()
                    self.error = None
                    return
                self._validate(target, plan["database"], document)
                # Compute the next checkpoint without making a provider request.
                key = "sheets" if sheets != target else "docs"
                repo = self.repository.source if key == "sheets" else self.repository.document
                calendar = source if key == "sheets" else document
                desired = target if key == "sheets" else [row[:7] for row in target]
                preview = _Preview(repo)
                next_rows = self._apply_one(preview, calendar, plan[key], desired, key == "docs")
                plan["next"] = {"sheets": deepcopy(plan["sheets"]), "docs": deepcopy(plan["docs"])}
                plan["next"][key] = next_rows
                self.database.checkpoint(plan)
                self._apply_one(repo, calendar, plan[key], desired, key == "docs")
            raise CalendarError("sync_plan_limit")
        except CalendarError as exc:
            self.error = exc.code
            self.database.conflict(exc.code, snapshots)
            raise
        except Exception as exc:
            self.error = "sync_unavailable"
            # Keep the durable plan; do not store provider exception text or credentials.
            self.database.operation_error("sync_unavailable")
            raise CalendarError("sync_unavailable", 502) from exc


class _Preview:
    """Use the planner's insertion rules without writing anything."""
    def __init__(self, repository):
        self.repository = repository

    def insertion(self, calendar, day):
        return self.repository.insertion(calendar, day)

    def update(self, *args):
        pass

    def insert(self, *args):
        pass

    def delete(self, *args):
        pass
