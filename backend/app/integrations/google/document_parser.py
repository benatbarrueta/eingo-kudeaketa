from app.models.calendar import Calendar, CalendarError, Row
from app.utils.basque_dates import MONTHS, parse
from .table_locator import locate


def cell_text(cell):
    return "\n".join(
        "".join(e.get("textRun", {}).get("content", "") for e in p["paragraph"].get("elements", []))
        .removesuffix("\n") for p in cell.get("content", []) if "paragraph" in p
    ).strip()


def plain(cell):
    content = cell.get("content", [])
    return bool(content) and all("paragraph" in p and all(
        "textRun" in e for e in p["paragraph"].get("elements", [])
    ) for p in content)


def gray(cell):
    rgb = cell.get("tableCellStyle", {}).get("backgroundColor", {}).get("color", {}).get("rgbColor")
    if not rgb:
        return False
    channels = [rgb.get(c, 0) for c in ("red", "green", "blue")]
    return max(channels) - min(channels) <= .035 and .15 <= min(channels) <= .95


def read(document, tab_id, table_index, year):
    tab, element = locate(document, tab_id, table_index)
    table = element["table"]
    count = table["columns"]
    rows = []
    columns = []
    for i, raw in enumerate(table.get("tableRows", [])):
        cells = raw["tableCells"]
        values = list(map(cell_text, cells))
        spans = [c.get("tableCellStyle", {}).get("columnSpan", 1) for c in cells]
        vertical = any(c.get("tableCellStyle", {}).get("rowSpan", 1) != 1 for c in cells)
        rectangular = len(cells) == count and all(s == 1 for s in spans) and not vertical
        textual = all(map(plain, cells))
        named_month = (
            bool(cells) and spans[0] == count and values[0].upper() in MONTHS
            and not any(values[1:])
            and (len(cells) == 1 or (len(cells) == count and all(span == 1 for span in spans[1:])))
        )
        day = None
        if i == 0:
            columns = [v.upper() for v in values]
            if (not rectangular or not textual or not all(columns)
                    or len(set(columns)) != count or not {"DATA", "HERRIA"} <= set(columns)):
                raise CalendarError("invalid_headers")
            kind = "header"
        elif (not vertical and textual and cells and all(map(gray, cells))
              and (named_month or (sum(spans) == count and not any(values)))):
            kind = "separator"
            if named_month:
                values, spans = values[:1], spans[:1]
        elif rectangular and textual and not any(map(gray, cells)):
            try:
                day = parse(values[columns.index("DATA")], year)
                kind = "event" if values[columns.index("HERRIA")] else "unknown"
            except ValueError:
                kind = "unknown"
        else:
            kind = "unknown"
        rows.append(Row(kind, values, cells, day, spans if not vertical else None, raw.get("tableRowStyle")))
    if not rows:
        raise CalendarError("invalid_headers")
    return Calendar(columns, rows, document.get("revisionId", ""), tab, element["startIndex"],
                    document.get("title", "EINGO Kudeaketa"))
