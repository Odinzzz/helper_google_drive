# helper-google-drive

Helpers for Google Drive and Google Docs using caller-supplied OAuth credentials.

## Install

```bash
pip install git+https://github.com/Odinzzz/helper_google_drive.git@v0.3.3
```

Replace the tag/branch with the version you want.

## Documentation

- Install: [docs/install.md](docs/install.md)
- Credentials: [docs/credentials.md](docs/credentials.md)
- Usage: [docs/usage.md](docs/usage.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## Quick example

```python
from helper_google_drive import list_files, list_tables, get_table_columns, update_table, append_row_to_table

credentials = {
    "access_token": "...",
    "refresh_token": "...",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "...",
    "client_secret": "...",
    "scopes": [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ],
}

files = list_files(credentials, folder_id="your-folder-id")

tables = list_tables(credentials, spreadsheet_id="spreadsheet-id")
columns = get_table_columns(credentials, spreadsheet_id="spreadsheet-id", table_name_or_id="Table1")
update_table(
    credentials,
    spreadsheet_id="spreadsheet-id",
    table_name_or_id="Table1",
    values=[["Value A", "Value B"]],
)
append_row_to_table(
    credentials,
    spreadsheet_id="spreadsheet-id",
    table_name_or_id="Table1",
    values=["Value A", "Value B"],
)
```
