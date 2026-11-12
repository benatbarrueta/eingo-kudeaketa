from google_auth_httplib2 import AuthorizedHttp
from httplib2 import Http, HttpLib2Error
from google.auth.exceptions import GoogleAuthError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.models.calendar import CalendarError
from .auth import credentials


class DocsClient:
    def __init__(self, settings):
        self.settings = settings

    def _execute(self, requests=None, revision=None):
        try:
            http = AuthorizedHttp(credentials(self.settings.credentials), http=Http(timeout=15))
            with build("docs", "v1", http=http, cache_discovery=False) as service:
                docs = service.documents()
                args = {"documentId": self.settings.document}
                if requests is None:
                    call = docs.get(**args, includeTabsContent=True)
                else:
                    call = docs.batchUpdate(**args, body={
                        "writeControl": {"requiredRevisionId": revision}, "requests": requests})
                return call.execute(num_retries=0)
        except HttpError as exc:
            status = exc.resp.status
            if status in (401, 403):
                raise CalendarError("google_access_denied", 502) from exc
            if status in (409, 412) or (status == 400 and b"revision" in exc.content.lower()):
                raise CalendarError("revision_conflict") from exc
            raise CalendarError("google_api_error", 502) from exc
        except (GoogleAuthError, HttpLib2Error, ValueError, OSError) as exc:
            raise CalendarError("google_unavailable", 502) from exc

    def get(self):
        return self._execute()

    def write(self, requests, revision):
        if not revision:
            raise CalendarError("missing_revision")
        return self._execute(requests, revision)
