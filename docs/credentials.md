# Credentials

This module expects OAuth credentials supplied by the caller. You can pass:

- A `dict` with the required fields
- A JSON string representing the same dict
- A `google.oauth2.credentials.Credentials` instance

## Required fields

- `access_token`
- `refresh_token`
- `token_uri`
- `client_id`
- `client_secret`
- `scopes` (list or space-delimited string)

## Optional fields

- `expiry` (ISO-8601 string)

## Notes

- Access tokens are refreshed automatically if expired and a `refresh_token` is present.
- Use `export_credentials()` to read the refreshed token values back.
