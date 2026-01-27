from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from helper_google_drive import append_row_to_table, get_table_columns, list_tables, update_table


DEFAULT_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _load_credentials(token_path: Path, scopes: Sequence[str]) -> Dict[str, Any]:
    data = json.loads(token_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("token file must contain a JSON object")

    # Ensure scopes exist for build_credentials validation.
    if not data.get("scopes") and not data.get("scope"):
        data["scopes"] = list(scopes)
    return data


def _parse_scopes(raw: str | None) -> List[str]:
    if not raw:
        return list(DEFAULT_SCOPES)
    return [part for part in raw.split() if part]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Google Sheets helpers.")
    parser.add_argument(
        "--token-path",
        default=".token.json",
        help="Path to credentials token JSON (default: .token.json).",
    )
    parser.add_argument(
        "--spreadsheet-id",
        default=os.environ.get("SPREADSHEET_ID", ""),
        help="Spreadsheet ID (or set SPREADSHEET_ID).",
    )
    parser.add_argument(
        "--table",
        dest="table_name_or_id",
        default=os.environ.get("TABLE_NAME_OR_ID", ""),
        help="Table name or tableId (or set TABLE_NAME_OR_ID).",
    )
    parser.add_argument(
        "--scopes",
        default=os.environ.get("SCOPES", ""),
        help="Space-delimited scopes to inject if missing in the token.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Actually write a small update into the table.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append a new row to the table (INSERT_ROWS).",
    )
    parser.add_argument(
        "--values",
        default="",
        help="JSON array-of-arrays for update_table values when using --write.",
    )
    parser.add_argument(
        "--start-row",
        type=int,
        default=0,
        help="Row offset from the table start for update_table (default: 0).",
    )
    parser.add_argument(
        "--start-column",
        type=int,
        default=0,
        help="Column offset from the table start for update_table (default: 0).",
    )

    args = parser.parse_args()

    token_path = Path(args.token_path)
    if not token_path.exists():
        parser.error(f"token file not found: {token_path}")

    if not args.spreadsheet_id:
        parser.error("spreadsheet id is required via --spreadsheet-id or SPREADSHEET_ID")

    scopes = _parse_scopes(args.scopes)
    credentials = _load_credentials(token_path, scopes)

    print("[1/3] Listing tables...")
    tables = list_tables(credentials, spreadsheet_id=args.spreadsheet_id)
    print(f"Found {len(tables)} table(s).")
    for table in tables:
        print(
            f"- {table.get('name') or '<no-name>'} "
            f"(id={table.get('tableId')}, range={table.get('range')})"
        )

    if not args.table_name_or_id:
        print(
            "\nNo --table provided. Set --table (or TABLE_NAME_OR_ID) to test columns and updates."
        )
        return 0

    print("\n[2/3] Fetching table columns...")
    try:
        columns = get_table_columns(
            credentials,
            spreadsheet_id=args.spreadsheet_id,
            table_name_or_id=args.table_name_or_id,
        )
    except ValueError as exc:
        print(f"Table not found: {args.table_name_or_id} ({exc}).")
        return 0
    print(f"Found {len(columns)} column(s).")
    for col in columns:
        print(
            f"- index={col.get('columnIndex')} "
            f"name={col.get('columnName')} type={col.get('columnType')}"
        )

    if not args.write and not args.append:
        print("\n[3/3] Skipping updates (pass --write or --append to enable).")
        return 0

    action = "append_row_to_table" if args.append else "update_table"
    print(f"\n[3/3] Running {action}...")
    if args.values:
        values = json.loads(args.values)
    else:
        now = datetime.now(timezone.utc).isoformat()
        values = [[f"SMOKE_TEST {now}"]]

    if args.append:
        # For append, accept either ["a","b"] or [["a","b"]]
        row_values = values[0] if values and isinstance(values[0], list) else values
        try:
            result = append_row_to_table(
                credentials,
                spreadsheet_id=args.spreadsheet_id,
                table_name_or_id=args.table_name_or_id,
                values=row_values,
            )
        except ValueError as exc:
            print(f"append_row_to_table failed safely: {exc}")
            return 0
        updated = result.get("updates", {}).get("updatedCells") or "?"
        print(f"append_row_to_table succeeded (updatedCells={updated}).")
        return 0

    try:
        result = update_table(
            credentials,
            spreadsheet_id=args.spreadsheet_id,
            table_name_or_id=args.table_name_or_id,
            values=values,
            start_row=args.start_row,
            start_column=args.start_column,
        )
    except ValueError as exc:
        print(f"update_table failed safely: {exc}")
        return 0
    updated = result.get("updatedCells") or result.get("updatedRows") or "?"
    print(f"update_table succeeded (updated={updated}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
