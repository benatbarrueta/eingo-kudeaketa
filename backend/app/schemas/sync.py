from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConflictResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(pattern=r"^[a-f0-9]{64}$")
    choices: dict[str, Literal["sheets", "docs", "database"]] = Field(min_length=1, max_length=90000)
