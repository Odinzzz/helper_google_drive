import io
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from helper_google_drive.database import get_latest_token, save_credentials

load_dotenv()


def build_credentials() -> Credentials:
    row = get_latest_token()
    if row is None:
        raise RuntimeError("Aucun token en base. Lancez /auth/google d'abord.")

    scopes = row["scopes"].split(",") if row["scopes"] else []
    creds = Credentials(
        token=row["access_token"],
        refresh_token=row["refresh_token"],
        token_uri=row["token_uri"],
        client_id=row["client_id"],
        client_secret=row["client_secret"],
        scopes=scopes,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        refresh_token_value = creds.refresh_token or row["refresh_token"]
        scopes_to_store = creds.scopes or scopes
        expires_at = creds.expiry.isoformat() if getattr(creds, "expiry", None) else None
        save_credentials(
            access_token=creds.token,
            refresh_token=refresh_token_value,
            token_uri=creds.token_uri,
            client_id=creds.client_id,
            client_secret=creds.client_secret,
            scopes=scopes_to_store,
            expires_at=expires_at,
        )

    return creds


def build_drive_service():
    creds = build_credentials()
    return build("drive", "v3", credentials=creds)


def list_folders(folder_id: str) -> List[Dict[str, str]]:
    service = build_drive_service()
    query = (
        f"'{folder_id}' in parents "
        "and mimeType = 'application/vnd.google-apps.folder' "
        "and trashed = false"
    )

    page_token = None
    folders: List[Dict[str, str]] = []

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, createdTime, modifiedTime)",
                pageToken=page_token,
            )
            .execute()
        )

        for file in response.get("files", []):
            folders.append(
                {
                    "id": file["id"],
                    "name": file["name"],
                    "createdTime": file.get("createdTime", ""),
                    "modifiedTime": file.get("modifiedTime", ""),
                }
            )

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return folders


def list_files(folder_id: str) -> List[Dict[str, str]]:
    service = build_drive_service()
    query = f"'{folder_id}' in parents and trashed = false"

    page_token = None
    files: List[Dict[str, str]] = []

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
                pageToken=page_token,
            )
            .execute()
        )

        for file in response.get("files", []):
            files.append(
                {
                    "id": file["id"],
                    "name": file["name"],
                    "mimeType": file.get("mimeType", ""),
                    "size": file.get("size", ""),
                    "modifiedTime": file.get("modifiedTime", ""),
                }
            )

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return files


def get_file_metadata(file_id: str) -> Dict[str, str]:
    service = build_drive_service()
    file = (
        service.files()
        .get(fileId=file_id, fields="id, name, mimeType")
        .execute()
    )
    return {
        "id": file.get("id", ""),
        "name": file.get("name", ""),
        "mimeType": file.get("mimeType", ""),
    }


def list_all_folders() -> List[Dict[str, str]]:
    service = build_drive_service()
    query = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"

    page_token = None
    folders: List[Dict[str, str]] = []

    while True:
        response = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
            )
            .execute()
        )

        for file in response.get("files", []):
            folders.append({"id": file["id"], "name": file["name"]})

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return folders


def download_file(file_id: str, destination: Optional[str] = None) -> str:
    """
    TÃ©lÃ©charge un fichier Drive en local et retourne le chemin crÃ©Ã©.
    Si destination n'est pas fournie, crÃ©e un fichier temporaire.
    """
    service = build_drive_service()
    request = service.files().get_media(fileId=file_id)

    if destination is None:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        destination = tmp.name
        tmp.close()

    with io.FileIO(destination, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    return destination


def delete_file(file_id: str) -> None:
    service = build_drive_service()
    service.files().delete(fileId=file_id).execute()


def upload_file_to_folder(
    file_path: str, folder_id: str, name_override: Optional[str] = None
) -> Dict[str, str]:
    service = build_drive_service()
    path = Path(file_path)
    media = MediaFileUpload(str(path), mimetype="application/pdf")
    metadata = {"name": name_override or path.name, "parents": [folder_id]}
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, name, webViewLink")
        .execute()
    )
    return {
        "id": created.get("id", ""),
        "name": created.get("name", ""),
        "webViewLink": created.get("webViewLink", ""),
    }


def rename_folder(folder_id: str, new_name: str) -> None:
    if not new_name.strip():
        raise ValueError("Nouveau nom invalide.")

    service = build_drive_service()
    updated = (
        service.files()
        .update(fileId=folder_id, body={"name": new_name}, fields="id, name")
        .execute()
    )
    # Sortie UTF-8 pour Ã©viter les UnicodeEncodeError en console Windows.
    sys.stdout.buffer.write(
        f"Dossier renommÃ© en '{updated['name']}' (ID: {updated['id']})\n".encode(
            "utf-8", errors="ignore"
        )
    )
    sys.stdout.flush()


def _usage() -> str:
    return (
        "Usage:\n"
        "  python helpers/drive.py               # liste les sous-dossiers de EVAL_FOLDER_ID\n"
        "  python helpers/drive.py files [FOLDER_ID]  # liste les fichiers d'un dossier\n"
        "  python helpers/drive.py rename FOLDER_ID \"Nouveau Nom\"\n"
        "  python helpers/drive.py download FILE_ID [DEST_PATH]\n"
    )


def _print_folders(folders: List[Dict[str, str]]):
    if not folders:
        print("Aucun dossier trouvÃ© dans ce dossier parent.")
        return
    for folder in folders:
        print(f"{folder['name']} ({folder['id']})")


def _print_files(files: List[Dict[str, str]]):
    if not files:
        print("Aucun fichier trouvÃ© dans ce dossier.")
        return
    for file in files:
        mime = file.get("mimeType") or "mime inconnu"
        size = file.get("size") or "-"
        print(f"{file['name']} ({file['id']}) - {mime} - size: {size}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "rename":
            if len(sys.argv) < 4:
                sys.exit(_usage())
            rename_folder(sys.argv[2], " ".join(sys.argv[3:]))
            sys.exit(0)
        if command == "files":
            target_folder = (
                sys.argv[2] if len(sys.argv) > 2 else os.environ.get("EVAL_FOLDER_ID")
            )
            if not target_folder:
                sys.exit("DÃ©finissez EVAL_FOLDER_ID ou fournissez un folder ID.")
            _print_files(list_files(target_folder))
            sys.exit(0)
        if command == "download":
            if len(sys.argv) < 3:
                sys.exit(_usage())
            file_id = sys.argv[2]
            destination = sys.argv[3] if len(sys.argv) > 3 else None
            path = download_file(file_id, destination)
            print(f"Fichier tÃ©lÃ©chargÃ© vers {path}")
            sys.exit(0)

    folder_id = os.environ.get("EVAL_FOLDER_ID")
    if not folder_id:
        sys.exit("DÃ©finissez EVAL_FOLDER_ID dans votre environnement ou .env")

    _print_folders(list_folders(folder_id))

