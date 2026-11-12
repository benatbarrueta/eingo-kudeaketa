import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    source: str
    year: int
    document: str = ""
    tab: str | None = None
    credentials: str = ""
    table: int = 0
    token: str = ""
    origin: str = "http://127.0.0.1:5173"

    spreadsheet: str = ""
    sheet_name: str = "Hoja 1"
    sheet_id: int = 0

    auto_sync: bool = False
    sync_interval: int = 15
    sync_state_path: str = ".local-sync/state.json"

    @classmethod
    def load(cls):
        load_dotenv()
        source = os.getenv("DATA_SOURCE", "mock")
        year = os.getenv("CALENDAR_YEAR") or ("2027" if source == "mock" else "")
        if source not in ("mock", "google", "sheets") or not year or not 1900 <= int(year) <= 9999:
            raise ValueError("Set DATA_SOURCE and a valid CALENDAR_YEAR")
        settings = cls(source, int(year), os.getenv("GOOGLE_DOCUMENT_ID", ""),
                       os.getenv("GOOGLE_TAB_ID") or None, os.getenv("GOOGLE_CREDENTIALS_PATH", ""),
                       int(os.getenv("GOOGLE_TABLE_INDEX", "0")), os.getenv("ADMIN_TOKEN", ""),
                       os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173"),
                       os.getenv("GOOGLE_SPREADSHEET_ID", ""),
                       os.getenv("GOOGLE_SHEET_NAME", "Hoja 1"),
                       int(os.getenv("GOOGLE_SHEET_ID", "0")),
                       os.getenv("AUTO_SYNC", "true").lower() == "true",
                       max(10, int(os.getenv("SYNC_INTERVAL_SECONDS", "15"))),
                       os.getenv("SYNC_STATE_PATH", ".local-sync/state.json"))
        if settings.table < 0 or (source != "mock" and (
                not settings.document or not settings.credentials or len(settings.token) < 32)):
            raise ValueError("Google mode requires document ID, credentials, and a 32+ character admin token")
        if source == "sheets" and not settings.spreadsheet:
            raise ValueError("Set GOOGLE_SPREADSHEET_ID")
        return settings
