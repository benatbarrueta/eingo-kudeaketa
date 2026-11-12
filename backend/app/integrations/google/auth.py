from google.oauth2 import service_account


def credentials(path):
    return service_account.Credentials.from_service_account_file(
        path, scopes=["https://www.googleapis.com/auth/documents"])
