from app.models.calendar import CalendarError
from app.utils.basque_dates import MONTHS


def insertion(calendar, date):
    events = [(i, r.date) for i, r in enumerate(calendar.rows) if r.kind == "event"]
    dates = [d for _, d in events]
    if dates != sorted(dates) or any(r.kind == "unknown" for r in calendar.rows):
        raise CalendarError("unsafe_structure")
    block = [(i, d) for i, d in events if (d.year, d.month) == (date.year, date.month)]
    if not block:
        headings = [
            (i, MONTHS.index(row.values[0].upper()) + 1)
            for i, row in enumerate(calendar.rows)
            if row.kind == "separator" and len(row.values) == 1 and row.values[0].upper() in MONTHS
        ]
        if date.month not in [month for _, month in headings]:
            raise CalendarError("month_without_block")
        months = [month for _, month in headings]
        if months != sorted(set(months)):
            raise CalendarError("unsafe_structure")
        anchor = next(i for i, month in headings if month == date.month)
        if any((i < anchor and day >= date) or (i > anchor and day <= date) for i, day in events):
            raise CalendarError("unsafe_structure")
        return anchor, True
    if block[-1][0] - block[0][0] + 1 != len(block):
        raise CalendarError("unsafe_structure")
    for i, d in block:
        if d > date:
            return i, False
    return block[-1][0], True
