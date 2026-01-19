# helper-google-drive

Helpers for Google Drive and Google Docs using caller-supplied OAuth credentials.

## Install

```
pip install helper-google-drive
```

## Documentation

- Install: [docs/install.md](docs/install.md)
- Credentials: [docs/credentials.md](docs/credentials.md)
- Usage: [docs/usage.md](docs/usage.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## Quick example

```python
from helper_google_drive import list_files

credentials = {
    "access_token": "...",
    "refresh_token": "...",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "...",
    "client_secret": "...",
    "scopes": ["https://www.googleapis.com/auth/drive"],
}

files = list_files(credentials, folder_id="your-folder-id")
```
