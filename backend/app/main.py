from contextlib import asynccontextmanager
from threading import Event, Thread
from pathlib import Path
import fcntl

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.calendar import router
from app.core.config import Settings
from app.core.security import WriteGuard
from app.models.calendar import CalendarError
from app.repositories.google_docs_repository import GoogleRepository
from app.repositories.google_sheets_repository import SheetsRepository
from app.repositories.synced_repository import SyncedRepository
from app.repositories.mock_repository import MockRepository
from app.services.bidirectional_sync import BidirectionalSync
from app.services.event_service import EventService


def create_app(settings=None, repo=None):
    settings = settings or Settings.load()
    if repo is None:
        if settings.source == "mock":
            repo = MockRepository(settings.year)
        elif settings.source == "sheets":
            repo = SyncedRepository(SheetsRepository(settings), GoogleRepository(settings))
        else:
            repo = GoogleRepository(settings)
    service = EventService(repo, settings.year)
    engine = None
    if settings.source == "sheets" and settings.auto_sync:
        identity = [settings.spreadsheet, settings.sheet_id, settings.document, settings.tab,
                    settings.table, settings.year]
        engine = BidirectionalSync(repo, settings.sync_state_path, settings.year, identity)
        service.synchronizer = engine

    @asynccontextmanager
    async def lifespan(app):
        stop = Event()
        thread = None
        lock_file = None
        if engine:
            path = Path(settings.sync_state_path)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            lock_file = open(str(path) + ".lock", "a")
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lock_file.close()
                raise RuntimeError("Run one EINGO backend process for automatic synchronization")

            def synchronize():
                while not stop.is_set():
                    with service.lock:
                        engine.tick()
                    stop.wait(settings.sync_interval)

            thread = Thread(target=synchronize, name="eingo-sync", daemon=True)
            thread.start()
        try:
            yield
        finally:
            stop.set()
            if thread:
                # Keep the cross-process lock until the active request has finished.
                import asyncio
                await asyncio.to_thread(thread.join)
            if lock_file:
                lock_file.close()

    app = FastAPI(title="EINGO Kudeaketa", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[settings.origin], allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type"])

    @app.exception_handler(CalendarError)
    async def calendar_error(request: Request, exc: CalendarError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        return JSONResponse({"error": {"code": "validation_error"}}, status_code=422)

    app.include_router(router(settings, service, WriteGuard(settings)))
    return app


app = create_app()
