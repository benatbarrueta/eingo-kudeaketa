from app.models.calendar import CalendarError


def locate(document, tab_id, table_index):
    def walk(tabs):
        for tab in tabs:
            yield tab
            yield from walk(tab.get("childTabs", []))

    if document.get("tabs"):
        tabs = list(walk(document["tabs"]))
        matches = [t for t in tabs if t["tabProperties"]["tabId"] == tab_id] if tab_id else tabs
        if len(matches) != 1:
            raise CalendarError("select_document_tab")
        tab = matches[0]
        tab_id = tab["tabProperties"]["tabId"]
        body = tab["documentTab"]["body"]
    elif tab_id:
        raise CalendarError("select_document_tab")
    else:
        body = document["body"]
    tables = [item for item in body.get("content", []) if "table" in item]
    if table_index >= len(tables):
        raise CalendarError("table_not_found")
    return tab_id, tables[table_index]
