from typing import Iterable, List, Sequence

from googleapiclient.discovery import build

from .drive import CredentialInput, build_credentials


def append_row(
    credentials: CredentialInput,
    *,
    spreadsheet_id: str,
    range_name: str,
    values: Sequence[object],
    value_input_option: str = "RAW",
    insert_data_option: str = "INSERT_ROWS",
) -> dict:
    """Append a single row to a Google Sheet and return the API response."""
    creds = build_credentials(credentials)
    service = build("sheets", "v4", credentials=creds)

    body = {"values": [list(values)]}
    return (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=value_input_option,
            insertDataOption=insert_data_option,
            body=body,
        )
        .execute()
    )
