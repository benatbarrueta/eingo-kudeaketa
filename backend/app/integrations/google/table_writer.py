from app.models.calendar import CalendarError


def location(calendar, index):
    return {"index": index, **tab_scope(calendar)}


def tab_scope(calendar):
    return {"tabId": calendar.tab} if calendar.tab else {}


def insert_row(calendar, anchor, below):
    return {"insertTableRow": {
        "tableCellLocation": {"tableStartLocation": location(calendar, calendar.start),
                              "rowIndex": anchor, "columnIndex": 0},
        "insertBelow": below,
    }}


def utf16(text):
    return len(text.encode("utf-16-le")) // 2


def fill_row(calendar, index, values, template):
    row = calendar.rows[index]
    if len(row.cells) != len(values) or any(row.values) or row.spans != [1] * len(values):
        raise CalendarError("unexpected_new_row")
    requests = []
    table_location = {"tableStartLocation": location(calendar, calendar.start),
                      "rowIndex": index, "columnIndex": 0}
    row_style = template.get("row_style", {}) if template else {}
    if row_style.get("minRowHeight"):
        requests.append({"updateTableRowStyle": {"tableStartLocation": location(calendar, calendar.start),
                          "rowIndices": [index], "tableRowStyle": {"minRowHeight": row_style["minRowHeight"]},
                          "fields": "minRowHeight"}})
    for col in reversed(range(len(values))):
        cell = row.cells[col]
        source = template["cells"][col] if template else {"content": cell["content"]}
        content = cell.get("content", [])
        if len(content) != 1 or "paragraph" not in content[0]:
            raise CalendarError("unexpected_new_row")
        paragraph = content[0]
        elements = paragraph["paragraph"].get("elements", [])
        if not elements or any(e.get("textRun", {}).get("content") != "\n" for e in elements):
            raise CalendarError("unexpected_new_row")
        pos = elements[0]["startIndex"]
        style = {k: v for k, v in source.get("tableCellStyle", {}).items()
                 if k in {"backgroundColor", "contentAlignment", "paddingTop", "paddingBottom",
                          "paddingLeft", "paddingRight"}}
        style.setdefault("backgroundColor", {"color": {"rgbColor": {"red": 1, "green": 1, "blue": 1}}})
        requests.append({"updateTableCellStyle": {"tableRange": {
            "tableCellLocation": {**table_location, "columnIndex": col}, "rowSpan": 1, "columnSpan": 1},
            "tableCellStyle": style, "fields": ",".join(style)}})
        value = values[col]
        if value:
            requests.append({"insertText": {"location": location(calendar, pos), "text": value}})
            source_paragraph = source["content"][0]["paragraph"]
            text_style = next((e["textRun"].get("textStyle", {}) for e in source_paragraph["elements"]
                               if e["textRun"]["content"].strip()), {})
            text_style = {k: v for k, v in text_style.items() if k != "link"}
            if text_style:
                requests.append({"updateTextStyle": {"range": {**tab_scope(calendar),
                    "startIndex": pos, "endIndex": pos + utf16(value)},
                    "textStyle": text_style, "fields": ",".join(text_style)}})
        source_style = source["content"][0]["paragraph"].get("paragraphStyle", {})
        style = {k: v for k, v in source_style.items() if k in {"alignment", "lineSpacing", "spaceAbove",
                  "spaceBelow", "indentStart", "indentEnd", "indentFirstLine", "namedStyleType", "direction"}}
        if style:
            span = {"startIndex": pos, "endIndex": pos + max(1, utf16(value))}
            if calendar.tab:
                span["tabId"] = calendar.tab
            requests.append({"updateParagraphStyle": {"range": span, "paragraphStyle": style,
                             "fields": ",".join(style)}})
    return requests


def delete_row(calendar, index):
    return {"deleteTableRow": {"tableCellLocation": {
        "tableStartLocation": location(calendar, calendar.start),
        "rowIndex": index,
        "columnIndex": 0,
    }}}


def edit_row(calendar, index, values):
    row = calendar.rows[index]
    requests = []
    # Work right to left so changing a cell does not invalidate earlier indices.
    for cell, old, new in reversed(list(zip(row.cells, row.values, values))):
        if old == new:
            continue
        paragraphs = cell["content"]
        elements = paragraphs[0]["paragraph"]["elements"]
        if not elements:
            raise CalendarError("unsafe_structure")
        start = elements[0]["startIndex"]
        end = paragraphs[-1]["endIndex"] - 1
        if end < start:
            raise CalendarError("unsafe_structure")
        if new:
            requests.append({"insertText": {"location": location(calendar, start), "text": new}})
        if end > start:
            offset = utf16(new)
            requests.append({"deleteContentRange": {"range": {
                **tab_scope(calendar), "startIndex": start + offset, "endIndex": end + offset,
            }}})
    return requests


def unmerge_row(calendar, index):
    return {"unmergeTableCells": {"tableRange": {
        "tableCellLocation": {
            "tableStartLocation": location(calendar, calendar.start),
            "rowIndex": index,
            "columnIndex": 0,
        },
        "rowSpan": 1,
        "columnSpan": len(calendar.columns),
    }}}
