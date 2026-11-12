from hmac import compare_digest
from threading import Lock
from time import monotonic
from app.models.calendar import CalendarError


class WriteGuard:
    def __init__(self, settings):
        self.settings = settings
        self.attempts = {}
        self.lock = Lock()

    def check(self, request):
        key = request.client.host if request.client else "unknown"
        now = monotonic()
        with self.lock:
            self.attempts = {k: v for k, v in self.attempts.items() if v[0] > now - 60}
            if len(self.attempts) >= 2048 and key not in self.attempts:
                raise CalendarError("rate_limited", 429)
            start, count = self.attempts.get(key, (now, 0))
            if count >= 20:
                raise CalendarError("rate_limited", 429)
            self.attempts[key] = (start, count + 1)
        if self.settings.source != "mock":
            supplied = request.headers.get("authorization", "").encode("utf-8")
            if not compare_digest(supplied, f"Bearer {self.settings.token}".encode("utf-8")):
                raise CalendarError("admin_required", 401)
