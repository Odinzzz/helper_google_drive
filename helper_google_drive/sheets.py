from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from googleapiclient.discovery import build

from .drive import CredentialInput, build_credentials


def _column_index_to_a1(index: int) -> str:
    """Convert a 0-based column index to A1 column letters."""
    if index < 0:
        raise ValueError("column index must be >= 0")
    result = []
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        result.append(chr(65 + remainder))
    return "".join(reversed(result))


def _grid_range_to_a1(sheet_title: str, grid_range: Dict[str, Any]) -> str:
    """Convert a GridRange object to an A1 range with sheet title."""
    start_row = grid_range.get("startRowIndex")
    end_row = grid_range.get("endRowIndex")
    start_col = grid_range.get("startColumnIndex")
    end_col = grid_range.get("endColumnIndex")

    if start_row is None or end_row is None or start_col is None or end_col is None:
        raise ValueError("grid range is missing start/end row/column indices")

    start_a1 = f"{_column_index_to_a1(start_col)}{start_row + 1}"
    end_a1 = f"{_column_index_to_a1(end_col - 1)}{end_row}"
    return f"{sheet_title}!{start_a1}:{end_a1}"


def _load_tables(credentials: CredentialInput, spreadsheet_id: str) -> List[Dict[str, Any]]:
    creds = build_credentials(credentials)
    service = build("sheets", "v4", credentials=creds)
    response = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            fields=(
                "sheets("
                "properties(sheetId,title,gridProperties(rowCount,columnCount)),"
                "tables(tableId,name,range,columnProperties)"
                ")"
            ),
        )
        .execute()
    )

    tables: List[Dict[str, Any]] = []
    for sheet in response.get("sheets", []):
        properties = sheet.get("properties", {})
        sheet_id = properties.get("sheetId")
        sheet_title = properties.get("title", "")
        grid_properties = properties.get("gridProperties", {}) or {}
        row_count = grid_properties.get("rowCount")
        column_count = grid_properties.get("columnCount")
        for table in sheet.get("tables", []) or []:
            entry = dict(table)
            entry["sheetId"] = sheet_id
            entry["sheetTitle"] = sheet_title
            entry["rowCount"] = row_count
            entry["columnCount"] = column_count
            tables.append(entry)
    return tables


def list_tables(credentials: CredentialInput, spreadsheet_id: str) -> List[Dict[str, Any]]:
    """List tables in a spreadsheet with their ids, names, and ranges."""
    tables = _load_tables(credentials, spreadsheet_id)
    results: List[Dict[str, Any]] = []
    for table in tables:
        range_a1 = _grid_range_to_a1(table["sheetTitle"], table["range"])
        results.append(
            {
                "tableId": table.get("tableId", ""),
                "name": table.get("name", ""),
                "sheetId": table.get("sheetId"),
                "sheetTitle": table.get("sheetTitle", ""),
                "range": range_a1,
            }
        )
    return results


def get_table_columns(
    credentials: CredentialInput,
    spreadsheet_id: str,
    *,
    table_name_or_id: str,
) -> List[Dict[str, Any]]:
    """Return table columns (name, index, type) for a given table."""
    tables = _load_tables(credentials, spreadsheet_id)
    for table in tables:
        if table.get("tableId") == table_name_or_id or table.get("name") == table_name_or_id:
            columns = table.get("columnProperties") or []
            return [
                {
                    "columnIndex": col.get("columnIndex"),
                    "columnName": col.get("columnName"),
                    "columnType": col.get("columnType"),
                }
                for col in columns
            ]
    raise ValueError("table not found")


def update_table(
    credentials: CredentialInput,
    *,
    spreadsheet_id: str,
    table_name_or_id: str,
    values: Sequence[Sequence[Any]],
    start_row: int = 0,
    start_column: int = 0,
    value_input_option: str = "RAW",
) -> Dict[str, Any]:
    """Update values inside a table by offsetting from its top-left cell."""
    if not values:
        raise ValueError("values must contain at least one row")
    max_cols = max((len(row) for row in values), default=0)
    if max_cols == 0:
        raise ValueError("values must contain at least one column")

    tables = _load_tables(credentials, spreadsheet_id)
    target: Optional[Dict[str, Any]] = None
    for table in tables:
        if table.get("tableId") == table_name_or_id or table.get("name") == table_name_or_id:
            target = table
            break
    if target is None:
        raise ValueError("table not found")

    grid_range = target["range"]
    if grid_range.get("startRowIndex") is None or grid_range.get("startColumnIndex") is None:
        raise ValueError("table range is missing start indices")

    start_row_index = grid_range["startRowIndex"] + start_row
    start_col_index = grid_range["startColumnIndex"] + start_column
    end_row_index = start_row_index + len(values)
    end_col_index = start_col_index + max_cols

    creds = build_credentials(credentials)
    service = build("sheets", "v4", credentials=creds)

    # Ensure the sheet grid is large enough for the requested update.
    current_row_count = int(target.get("rowCount") or 0)
    current_col_count = int(target.get("columnCount") or 0)
    needed_row_count = max(current_row_count, end_row_index)
    needed_col_count = max(current_col_count, end_col_index)

    if needed_row_count > current_row_count or needed_col_count > current_col_count:
        if target.get("sheetId") is None:
            raise ValueError("table sheetId is missing; cannot resize sheet grid")
        resize_requests: List[Dict[str, Any]] = [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": target["sheetId"],
                        "gridProperties": {
                            "rowCount": needed_row_count,
                            "columnCount": needed_col_count,
                        },
                    },
                    "fields": "gridProperties(rowCount,columnCount)",
                }
            }
        ]
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": resize_requests},
        ).execute()

    range_a1 = _grid_range_to_a1(
        target["sheetTitle"],
        {
            "startRowIndex": start_row_index,
            "endRowIndex": end_row_index,
            "startColumnIndex": start_col_index,
            "endColumnIndex": end_col_index,
        },
    )

    body = {"values": [list(row) for row in values]}
    return (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_a1,
            valueInputOption=value_input_option,
            body=body,
        )
        .execute()
    )


def append_row_to_table(
    credentials: CredentialInput,
    *,
    spreadsheet_id: str,
    table_name_or_id: str,
    values: Sequence[Any],
    value_input_option: str = "RAW",
) -> Dict[str, Any]:
    """Append a single row to a table, always inserting new rows if needed."""
    tables = _load_tables(credentials, spreadsheet_id)
    target: Optional[Dict[str, Any]] = None
    for table in tables:
        if table.get("tableId") == table_name_or_id or table.get("name") == table_name_or_id:
            target = table
            break
    if target is None:
        raise ValueError("table not found")

    table_range_a1 = _grid_range_to_a1(target["sheetTitle"], target["range"])

    creds = build_credentials(credentials)
    service = build("sheets", "v4", credentials=creds)
    body = {"values": [list(values)]}
    return (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=table_range_a1,
            valueInputOption=value_input_option,
            insertDataOption="INSERT_ROWS",
            body=body,
        )
        .execute()
    )


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
