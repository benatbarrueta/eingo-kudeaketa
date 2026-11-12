import re
from datetime import date
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=240)]


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    town: Annotated[ShortText, Field(min_length=1)]
    fields: dict[ShortText, ShortText] = Field(default_factory=dict, max_length=50)

    @field_validator("date", mode="before")
    @classmethod
    def iso_only(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Expected YYYY-MM-DD")
        return value

    @field_validator("town", "fields")
    @classmethod
    def single_line(cls, value):
        parts = [value] if isinstance(value, str) else list(value) + list(value.values())
        if any(re.search(r"[\x00-\x1f\x7f-\x9f\u2028\u2029\ud800-\udfff\ue000-\uf8ff]", part) for part in parts):
            raise ValueError("Unsupported characters")
        return value


class EventTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected: list[str] = Field(max_length=200)


class EventUpdate(EventCreate):
    expected: list[str] = Field(max_length=200)
