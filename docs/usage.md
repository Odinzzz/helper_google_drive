# Usage

```python
from helper_google_drive import (
    build_credentials,
    append_row_to_table,
    get_table_columns,
    list_files,
    list_folders,
    list_tables,
    download_file,
    upload_file_to_folder,
    rename_folder,
    create_document_in_folder,
    append_row,
    update_table,
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
        "https://www.googleapis.com/auth/spreadsheets",
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

tables = list_tables(credentials, spreadsheet_id="spreadsheet-id")
columns = get_table_columns(credentials, spreadsheet_id="spreadsheet-id", table_name_or_id="Table1")
update_table(
    credentials,
    spreadsheet_id="spreadsheet-id",
    table_name_or_id="Table1",
    values=[["Value A", "Value B"]],
)

# Always append a new row to the table (inserts rows as needed)
append_row_to_table(
    credentials,
    spreadsheet_id="spreadsheet-id",
    table_name_or_id="Table1",
    values=["Value A", "Value B"],
)

# If you want to store refreshed tokens
creds = build_credentials(credentials)
fresh = export_credentials(creds)
```
