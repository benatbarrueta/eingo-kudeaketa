from google.oauth2 import service_account
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import GoogleAuthError
from httplib2 import Http, HttpLib2Error

from app.models.calendar import CalendarError


class SheetsClient:
    def __init__(self, settings):
        self.settings = settings

    def execute(self, requests=None):
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.settings.credentials,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            with build("sheets", "v4", http=AuthorizedHttp(credentials, http=Http(timeout=15)),
                       cache_discovery=False) as service:
                sheets = service.spreadsheets()
                if requests is None:
                    call = sheets.get(spreadsheetId=self.settings.spreadsheet,
                                      ranges=[f"'{self.settings.sheet_name.replace(chr(39), chr(39)*2)}'!A1:I10000"],
                                      includeGridData=True)
                else:
                    call = sheets.batchUpdate(spreadsheetId=self.settings.spreadsheet,
                                              body={"requests": requests})
                return call.execute(num_retries=0)
        except HttpError as exc:
            code = "sheets_access_denied" if exc.resp.status in (401, 403) else "sheets_api_error"
            raise CalendarError(code, 502) from exc
        except (GoogleAuthError, HttpLib2Error, OSError, ValueError) as exc:
            raise CalendarError("sheets_unavailable", 502) from exc
