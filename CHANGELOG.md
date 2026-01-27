# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

## [Unreleased]

## [0.3.3] - 2026-01-27

### Added
- Added helpers to `list_tables`, `get_table_columns`, and `update_table`.
- Added `append_row_to_table` to fill the first empty row, or insert a new row if none exist.

## [0.1.01] - 2026-01-19

### Added
- Initial packaging as a pip-installable module.
- Drive/Docs helpers now require caller-supplied credentials.
- Added Google Sheets helper for appending rows.

### Removed
- Removed database and PDF helpers.
