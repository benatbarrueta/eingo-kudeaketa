from fastapi import APIRouter, Request, Response
from app.models.calendar import CalendarError
from app.schemas.events import EventCreate, EventTarget, EventUpdate
from app.schemas.responses import Config, DocumentStatus, Events, EventSaved, Ok, Table


def router(settings, service, guard):
    api = APIRouter(prefix="/api")

    @api.post("/sheets/import-document", response_model=Table)
    def import_document(request: Request):
        guard.check(request)
        with service.lock:
            if settings.source != "sheets":
                raise CalendarError("sheets_only", 404)
            return service.repo.import_document().public()

    @api.post("/document/sync", response_model=Table)
    def synchronize(request: Request):
        guard.check(request)
        with service.lock:
            if settings.source != "sheets":
                raise CalendarError("sheets_only", 404)
            if service.synchronizer:
                service.synchronize()
                return service.repo.document.read().public()
            return service.repo.synchronize().public()

    @api.get("/sync/status")
    def synchronization_status():
        engine = service.synchronizer
        return {"enabled": engine is not None,
                "lastSuccess": engine.last_success if engine else None,
                "error": engine.error if engine else None,
                "intervalSeconds": settings.sync_interval}

    @api.get("/health", response_model=Ok)
    def health():
        return {"ok": True}

    @api.get("/config", response_model=Config)
    def config():
        url = f"https://docs.google.com/document/d/{settings.document}/edit"
        if settings.tab:
            url += f"?tab={settings.tab}"
        return {"year": settings.year, "source": settings.source,
                "documentUrl": url if settings.source != "mock" else None,
                "spreadsheetUrl": f"https://docs.google.com/spreadsheets/d/{settings.spreadsheet}/edit" if settings.source == "sheets" else None}

    @api.get("/events", response_model=Events)
    def events():
        calendar = service.repo.read()
        return {"events": calendar.events(), "columns": calendar.columns, "title": calendar.title}

    @api.post("/events", status_code=201, response_model=EventSaved,
              responses={200: {"model": EventSaved, "description": "Identical event already exists"}})
    def create(event: EventCreate, request: Request, response: Response):
        guard.check(request)
        result = service.create(event)
        if not result["created"]:
            response.status_code = 200
        return result

    @api.post("/events/{index}/edit", response_model=EventSaved)
    def edit(index: int, event: EventUpdate, request: Request):
        guard.check(request)
        return service.update(index, event)

    @api.post("/events/{index}/delete", response_model=Table)
    def delete(index: int, target: EventTarget, request: Request):
        guard.check(request)
        return service.delete(index, target)

    @api.get("/document/structure", response_model=Table)
    def structure():
        document = getattr(service.repo, "document", service.repo)
        return document.read().public()

    @api.get("/calendar", response_model=Table)
    def calendar():
        return service.repo.read().public()

    @api.get("/document/status", response_model=DocumentStatus)
    def status():
        calendar = service.repo.read()
        return {"source": settings.source, "connected": settings.source != "mock",
                "writable": not getattr(service.repo, "needs_review", False)
                and not any(r.kind == "unknown" for r in calendar.rows)}

    @api.post("/demo/reset", response_model=Ok)
    def reset(request: Request):
        if settings.source != "mock":
            raise CalendarError("demo_only", 404)
        guard.check(request)
        service.reset()
        return {"ok": True}

    return api
