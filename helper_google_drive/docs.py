from typing import Iterable

from googleapiclient.discovery import build

from .drive import CredentialInput, build_credentials


def create_document_in_folder(
    credentials: CredentialInput,
    *,
    folder_id: str,
    title: str,
    lines: Iterable[str],
) -> dict:
    """Create a Google Doc in a folder and insert the provided lines."""
    creds = build_credentials(credentials)
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
