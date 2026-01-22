# Usage

```python
from helper_google_drive import (
    build_credentials,
    list_files,
    list_folders,
    download_file,
    upload_file_to_folder,
    rename_folder,
    create_document_in_folder,
    append_row,
    export_credentials,
)

credentials = {
    "access_token": "...",
    "refresh_token": "...",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "...",
    "client_secret": "...",
    "scopes": [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
    ],
}

folders = list_folders(credentials, folder_id="parent-folder-id")
files = list_files(credentials, folder_id="parent-folder-id")

local_path = download_file(credentials, file_id="file-id")

uploaded = upload_file_to_folder(
    credentials,
    file_path="report.pdf",
    folder_id="parent-folder-id",
)

renamed = rename_folder(credentials, folder_id="folder-id", new_name="New Name")

created = create_document_in_folder(
    credentials,
    folder_id="parent-folder-id",
    title="My Doc",
    lines=["Hello", "World"],
)

append_row(
    credentials,
    spreadsheet_id="spreadsheet-id",
    range_name="Sheet1!A:Z",
    values=["Col A", "Col B", "Col C"],
)

# If you want to store refreshed tokens
creds = build_credentials(credentials)
fresh = export_credentials(creds)
```
