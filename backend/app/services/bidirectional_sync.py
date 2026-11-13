"""Three-way reconciliation using a private, durable last synchronized snapshot."""
from difflib import SequenceMatcher
from collections import Counter
from pathlib import Path
import json
import os
import tempfile

from app.models.calendar import CalendarError
from app.utils.basque_dates import format_date, parse
from app.services.chronological_service import insertion


def align(base, current, width=7):
    matcher = SequenceMatcher(a=[tuple(row[:width]) for row in base],
                              b=[tuple(row[:width]) for row in current], autojunk=False)
    mapped = {}
    inserted = {}
    for kind, start, end, new_start, new_end in matcher.get_opcodes():
        old_count, new_count = end - start, new_end - new_start
        if kind == "equal" or (kind == "replace" and old_count == new_count):
            for offset in range(old_count):
                mapped[start + offset] = current[new_start + offset]
        elif kind == "delete":
            for index in range(start, end):
                mapped[index] = None
        elif kind == "insert":
            inserted[start] = current[new_start:new_end]
        else:
            # Different-sized replacements cannot identify the original events reliably.
            raise CalendarError("sync_conflict")
    if inserted and any(row is None for row in mapped.values()):
        # A moved/reidentified row could otherwise lose its private Sheets fields.
        raise CalendarError("sync_ambiguous_events")
    return mapped, inserted


def merge(base, sheets, docs, width=7):
    if docs == [row[:width] for row in sheets]:
        return sheets
    duplicates = Counter(tuple(row[:width]) for row in base)
    if any(count > 1 for count in duplicates.values()):
        raise CalendarError("sync_ambiguous_events")
    source, source_added = align(base, sheets, width)
    document, document_added = align(base, docs, width)
    result = []
    for index in range(len(base) + 1):
        left = source_added.get(index, [])
        right = document_added.get(index, [])
        if left and right and [row[:width] for row in left] != right:
            raise CalendarError("sync_conflict")
        result.extend(left or [row + [""] * (9 - width) for row in right])
        if index == len(base):
            break
        original = base[index]
        left, right = source[index], document[index]
        if left is None or right is None:
            survivor = right if left is None else left
            expected = original[:width] if left is None else original
            if survivor is not None and survivor != expected:
                raise CalendarError("sync_conflict")
            continue
        row = []
        for old, sheet_value, doc_value in zip(original[:width], left[:width], right):
            if sheet_value == doc_value or doc_value == old:
                row.append(sheet_value)
            elif sheet_value == old:
                row.append(doc_value)
            else:
                raise CalendarError("sync_conflict")
        result.append(row + left[width:9])
    return result


class BidirectionalSync:
    def __init__(self, repository, path, year, identity):
        self.repository = repository
        self.path = Path(path)
        self.year = year
        self.identity = identity
        self.error = None
        self.last_success = None

    def _save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".sync-")
        try:
            with os.fdopen(descriptor, "w") as output:
                json.dump({"identity": self.identity, **state}, output, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _rows(self, calendar, width):
        if any(row.kind == "unknown" for row in calendar.rows):
            raise CalendarError("unsafe_structure")
        result = []
        for row in calendar.rows:
            if row.kind == "event":
                result.append([format_date(row.date), *row.values[1:width]])
        return result

    def _read(self):
        source = self.repository.source.read()
        document = self.repository.document.read()
        self.repository._project(source, document)
        return source, document, self._rows(source, 9), self._rows(document, 7)

    def _apply_one(self, repo, calendar, current, target, is_document):
        matcher = SequenceMatcher(a=list(map(tuple, current)), b=list(map(tuple, target)),
                                  autojunk=False)
        kind, start, end, new_start, new_end = next(
            code for code in matcher.get_opcodes() if code[0] != "equal")
        events = calendar.events()
        if kind == "replace" and end - start == new_end - new_start:
            new = target[new_start]
            old_day = events[start]["date"]
            new_day = parse(new[0], self.year)
            # A date crossing month boundaries needs a row in the new month block.
            if old_day.month == new_day.month:
                repo.update(calendar, events[start]["id"], new)
                return current[:start] + [new] + current[start + 1:]
        if kind in ("delete", "replace"):
            repo.delete(calendar, events[start]["id"])
            return current[:start] + current[start + 1:]
        new = target[new_start]
        day = parse(new[0], self.year)
        if start < len(events) and (not is_document or events[start]["date"].month == day.month):
            anchor, below = events[start]["id"], False
        elif is_document:
            anchor, below = insertion(calendar, day)
        else:
            anchor, below = repo.insertion(calendar, day)
        repo.insert(calendar, anchor, below, new)
        return current[:start] + [new] + current[start:]

    def run(self):
        from datetime import datetime, timezone
        source, document, sheets, docs = self._read()
        state = json.loads(self.path.read_text()) if self.path.exists() else None
        if state and state.get("identity") != self.identity:
            raise CalendarError("sync_state_mismatch")
        if state and "target" in state and docs == [row[:7] for row in sheets]:
            # Both files agreeing is also an explicit manual conflict resolution.
            self._save({"base": sheets})
            state = None
        if state is None:
            if [row[:7] for row in sheets] != docs:
                raise CalendarError("sync_initial_mismatch")
            self._save({"base": sheets})
        elif "target" not in state:
            target = merge(state["base"], sheets, docs)
            target.sort(key=lambda row: parse(row[0], self.year))
            # Validate the whole plan before writing anything.
            from app.utils.basque_dates import MONTHS
            named_months = {MONTHS.index(row.values[0].upper()) + 1
                            for row in document.rows if row.kind == "separator"
                            and len(row.values) == 1 and row.values[0].upper() in MONTHS}
            existing_months = {event["date"].month for event in document.events()}
            for row in target:
                day = parse(row[0], self.year)
                if day.year != self.year or not row[1]:
                    raise CalendarError("unsafe_structure")
                if day.month not in named_months | existing_months:
                    raise CalendarError("month_without_block")
            state = {"base": state["base"], "target": target, "sheets": sheets, "docs": docs}
            self._save(state)
        if state and "target" in state:
            target = state["target"]
            # Each mutation is checkpointed. A concurrent external change stops the plan.
            for _ in range(1000):
                source, document, sheets, docs = self._read()
                if sheets != state["sheets"] or docs != state["docs"]:
                    raise CalendarError("sync_conflict")
                if sheets == target and docs == [row[:7] for row in target]:
                    self._save({"base": target})
                    self.repository.sync_pending = False
                    break
                if sheets != target:
                    state["sheets"] = self._apply_one(self.repository.source, source, sheets, target, False)
                else:
                    state["docs"] = self._apply_one(self.repository.document, document, docs,
                                    [row[:7] for row in target], True)
                self._save(state)
            else:
                raise CalendarError("sync_plan_limit")
        self.last_success = datetime.now(timezone.utc).isoformat()
        self.error = None

    def tick(self):
        try:
            self.run()
        except CalendarError as exc:
            self.error = exc.code
        except Exception:
            self.error = "sync_unavailable"
