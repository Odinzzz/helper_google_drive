# helper-google-drive

Helpers for Google Drive and Google Docs using caller-supplied OAuth credentials.

## Install

```
pip install git+https://github.com/Odinzzz/helper_google_drive.git
```

## Credentials format

Provide credentials as a dict or JSON string with at least:

- access_token
- refresh_token
- token_uri
- client_id
- client_secret
- scopes (list or space-delimited string)
- expiry (optional ISO-8601 string)

## Usage

```python
from helper_google_drive import list_files, create_document_in_folder

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

files = list_files(credentials, folder_id="your-folder-id")

created = create_document_in_folder(
    credentials,
    folder_id="your-folder-id",
    title="My Doc",
    lines=["Hello", "World"],
)
```
