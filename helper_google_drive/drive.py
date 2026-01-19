from __future__ import annotations

import io
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

CredentialInput = Union[Credentials, Mapping[str, Any], str]
_REQUIRED_FIELDS = ("access_token", "refresh_token", "token_uri", "client_id", "client_secret")


def _parse_expiry(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO-8601 expiry timestamps, returning a datetime or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("expiry must be an ISO-8601 string") from exc


def _normalize_scopes(value: Any) -> List[str]:
    """Normalize scopes from a string or iterable into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [item for item in value.split() if item]
    if isinstance(value, Mapping):
        raise TypeError("scopes must be a list or space-delimited string")
    if isinstance(value, Iterable):
        return [str(item) for item in value if item]
    raise TypeError("scopes must be a list or space-delimited string")


def _coerce_credentials_data(credentials: CredentialInput) -> Dict[str, Any]:
    """Coerce credentials input into a plain dict of fields."""
    if isinstance(credentials, Credentials):
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes or []),
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }
    if isinstance(credentials, str):
        data = json.loads(credentials)
        if not isinstance(data, dict):
            raise ValueError("credentials JSON must be an object")
        return data
    if isinstance(credentials, Mapping):
        return dict(credentials)
    raise TypeError("credentials must be a Credentials, mapping, or JSON string")


def build_credentials(
    credentials: CredentialInput,
    *,
    scopes: Optional[Sequence[str]] = None,
) -> Credentials:
    """Build google Credentials from dict/JSON/instance with validation."""
    data = _coerce_credentials_data(credentials)
    missing = [field for field in _REQUIRED_FIELDS if not data.get(field)]
    if missing:
        raise ValueError(f"missing credentials fields: {', '.join(missing)}")

    scope_values = list(scopes) if scopes is not None else _normalize_scopes(
        data.get("scopes") or data.get("scope")
    )
    if not scope_values:
        raise ValueError("scopes are required in credentials data or via scopes argument")

    expiry = _parse_expiry(data.get("expiry") or data.get("expires_at"))
    creds = Credentials(
        token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=scope_values,
        expiry=expiry,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return creds


def export_credentials(creds: Credentials) -> Dict[str, Any]:
    """Export a Credentials object into a serializable dict."""
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or []),
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


def build_drive_service(credentials: CredentialInput):
    """Build an authenticated Google Drive API service client."""
    creds = build_credentials(credentials)
    return build("drive", "v3", credentials=creds)


def list_folders(credentials: CredentialInput, folder_id: str) -> List[Dict[str, str]]:
    """List child folders in a given Drive folder."""
    service = build_drive_service(credentials)
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


def list_files(credentials: CredentialInput, folder_id: str) -> List[Dict[str, str]]:
    """List files in a given Drive folder."""
    service = build_drive_service(credentials)
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


def get_file_metadata(credentials: CredentialInput, file_id: str) -> Dict[str, str]:
    """Fetch basic metadata for a Drive file (id, name, mimeType)."""
    service = build_drive_service(credentials)
    file = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    return {
        "id": file.get("id", ""),
        "name": file.get("name", ""),
        "mimeType": file.get("mimeType", ""),
    }


def list_all_folders(credentials: CredentialInput) -> List[Dict[str, str]]:
    """List all folders visible to the authenticated user."""
    service = build_drive_service(credentials)
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


def download_file(
    credentials: CredentialInput,
    file_id: str,
    destination: Optional[str] = None,
) -> str:
    """Download a Drive file; returns the local path used."""
    service = build_drive_service(credentials)
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


def delete_file(credentials: CredentialInput, file_id: str) -> None:
    """Delete a Drive file by ID."""
    service = build_drive_service(credentials)
    service.files().delete(fileId=file_id).execute()


def upload_file_to_folder(
    credentials: CredentialInput,
    file_path: str,
    folder_id: str,
    name_override: Optional[str] = None,
    mime_type: str = "application/pdf",
) -> Dict[str, str]:
    """Upload a file into a Drive folder and return id/name/webViewLink."""
    service = build_drive_service(credentials)
    path = Path(file_path)
    media = MediaFileUpload(str(path), mimetype=mime_type)
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


def rename_folder(credentials: CredentialInput, folder_id: str, new_name: str) -> Dict[str, str]:
    """Rename a Drive folder by ID and return the id/name."""
    if not new_name.strip():
        raise ValueError("new_name must not be empty")

    service = build_drive_service(credentials)
    updated = (
        service.files()
        .update(fileId=folder_id, body={"name": new_name}, fields="id, name")
        .execute()
    )
    return {"id": updated.get("id", ""), "name": updated.get("name", "")}
