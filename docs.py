from typing import Iterable

from googleapiclient.discovery import build

from helper_google_drive.drive import build_credentials


def create_document_in_folder(
    *,
    folder_id: str,
    title: str,
    lines: Iterable[str],
) -> dict:
    """
    CrÃ©e un Google Doc dans un dossier Drive donnÃ© et insÃ¨re le contenu fourni.
    Retourne les mÃ©tadonnÃ©es du fichier crÃ©Ã© (id, name, webViewLink).
    """
    creds = build_credentials()
    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)

    file_metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id],
    }
    created = (
        drive_service.files()
        .create(body=file_metadata, fields="id, name, webViewLink")
        .execute()
    )

    content = "\n".join(lines)
    requests = [
        {
            "insertText": {
                "location": {"index": 1},
                "text": content,
            }
        }
    ]
    docs_service.documents().batchUpdate(
        documentId=created["id"], body={"requests": requests}
    ).execute()

    return created

