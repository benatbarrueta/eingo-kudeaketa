from typing import Protocol

from app.models.calendar import Calendar


class Repository(Protocol):
    def read(self) -> Calendar: ...
    def insert(self, calendar, anchor, below, values) -> Calendar: ...
