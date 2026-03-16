import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


FOLDER_ID = "19r0iMAhoEFYigbs1biUNRbWYko5EehAQ"
SERVICE_ACCOUNT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "voice-to-text-466011-71e41c319550.json",
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]


def _get_credentials():
    """
    Загружает учетные данные сервисного аккаунта.
    """
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"Файл сервисного аккаунта не найден: {SERVICE_ACCOUNT_FILE}"
        )

    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )


def upload_excel_to_drive(excel_path: str) -> str:
    """
    Загружает .xlsx файл в Google Drive в указанную папку.

    Args:
        excel_path: путь к локальному .xlsx файлу результата

    Returns:
        URL загруженного файла на Google Drive
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Файл не найден: {excel_path}")

    creds = _get_credentials()
    drive_service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name": os.path.basename(excel_path),
        "parents": [FOLDER_ID],
    }
    media = MediaFileUpload(
        excel_path,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        resumable=False,
    )

    file = (
        drive_service.files()
        .create(body=file_metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )

    return file.get("webViewLink", f"https://drive.google.com/file/d/{file['id']}")

