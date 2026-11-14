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
    origin: str = "http://127.0.0.1:5173"

    spreadsheet: str = ""
    sheet_name: str = "Hoja 1"
    sheet_id: int = 0

    auto_sync: bool = False
    sync_interval: int = 15
    sync_state_path: str = ".local-sync/state.json"
    database_path: str = ".local-data/eingo.sqlite3"
    google_sync: bool = False
    auto_backup: bool = True
    backup_directory: str = ".local-data/backups"
    backup_interval: int = 3600
    backup_keep: int = 48

    @classmethod
    def load(cls):
        load_dotenv()
        source = os.getenv("DATA_SOURCE", "mock")
        year = os.getenv("CALENDAR_YEAR") or ("2027" if source == "mock" else "")
        if source not in ("mock", "google", "sheets", "database") or not year or not 1900 <= int(year) <= 9999:
            raise ValueError("Set DATA_SOURCE and a valid CALENDAR_YEAR")
        settings = cls(source, int(year), os.getenv("GOOGLE_DOCUMENT_ID", ""),
                       os.getenv("GOOGLE_TAB_ID") or None, os.getenv("GOOGLE_CREDENTIALS_PATH", ""),
                       int(os.getenv("GOOGLE_TABLE_INDEX", "0")),
                       os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173"),
                       os.getenv("GOOGLE_SPREADSHEET_ID", ""),
                       os.getenv("GOOGLE_SHEET_NAME", "Hoja 1"),
                       int(os.getenv("GOOGLE_SHEET_ID", "0")),
                       os.getenv("AUTO_SYNC", "true").lower() == "true",
                       max(10, int(os.getenv("SYNC_INTERVAL_SECONDS", "15"))),
                       os.getenv("SYNC_STATE_PATH", ".local-sync/state.json"),
                       os.getenv("DATABASE_PATH", ".local-data/eingo.sqlite3"),
                       os.getenv("GOOGLE_SYNC", "false").lower() == "true",
                       os.getenv("AUTO_BACKUP", "true").lower() == "true",
                       os.getenv("BACKUP_DIRECTORY", ".local-data/backups"),
                       int(os.getenv("BACKUP_INTERVAL_SECONDS", "3600")),
                       int(os.getenv("BACKUP_KEEP", "48")))
        uses_google = source in ("google", "sheets") or (source == "database" and settings.google_sync)
        if settings.table < 0 or (uses_google and (
                not settings.document or not settings.credentials)):
            raise ValueError("Google mode requires document ID and credentials")
        if (source == "sheets" or (source == "database" and settings.google_sync)) and not settings.spreadsheet:
            raise ValueError("Set GOOGLE_SPREADSHEET_ID")
        if not settings.database_path.strip():
            raise ValueError("Set DATABASE_PATH")
        if settings.backup_interval < 60 or not 1 <= settings.backup_keep <= 10000 or not settings.backup_directory.strip():
            raise ValueError("Set a valid backup directory, interval (at least 60 seconds) and retention")
        return settings
