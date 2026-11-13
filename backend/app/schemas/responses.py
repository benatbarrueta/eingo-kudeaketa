from datetime import date as Date
from typing import Literal

from pydantic import BaseModel


class Event(BaseModel):
    id: int
    date: Date
    values: list[str]
    eventId: str | None = None
    version: int | None = None


class TableRow(BaseModel):
    kind: Literal["header", "event", "separator", "unknown"]
    values: list[str]
    spans: list[int] | None
    date: Date | None
    eventId: str | None = None
    version: int | None = None


class Table(BaseModel):
    title: str
    columns: list[str]
    rows: list[TableRow]


class Events(BaseModel):
    title: str
    columns: list[str]
    events: list[Event]


class EventSaved(BaseModel):
    event: Event
    table: Table
    created: bool


class Config(BaseModel):
    year: int
    source: Literal["mock", "google", "sheets", "database"]
    googleSync: bool = False
    documentUrl: str | None
    spreadsheetUrl: str | None = None


class DocumentStatus(BaseModel):
    source: Literal["mock", "google", "sheets", "database"]
    connected: bool
    writable: bool


class Ok(BaseModel):
    ok: bool
