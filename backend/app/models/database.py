"""Persistent entities. Google credentials never belong to these models."""
from dataclasses import dataclass
from datetime import date, datetime


COLUMNS = ["DATA", "HERRIA", "NOR", "ORDUA", "FAKTURAZIOA", "KONFIRM", "AZALPENA", "WAWA", "WEWE"]


@dataclass(frozen=True)
class Event:
    id: str
    configuration_id: str
    date: date
    town: str
    nor: str
    time: str
    billing: str
    confirmation: str
    description: str
    wawa: str
    wewe: str
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True)
class SyncConfiguration:
    id: str
    year: int
    identity: list
    initialized: bool
    revision: int


@dataclass(frozen=True)
class SyncState:
    event_id: str
    ordinal: int
    values: list[str]
    sheet_row: int
    document_row: int
    verified_at: str


@dataclass(frozen=True)
class SyncOperation:
    id: str
    configuration_id: str
    status: str
    payload: dict
    attempts: int
    error: str | None


@dataclass(frozen=True)
class SyncConflict:
    id: str
    configuration_id: str
    event_id: str | None
    code: str
    snapshots: dict
    resolved_at: str | None


@dataclass(frozen=True)
class EventChange:
    id: str
    event_id: str
    action: str
    origin: str
    before: list[str] | None
    after: list[str] | None
    created_at: str
