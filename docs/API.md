# API and storage

The browser uses these endpoints:

- `GET /` — file-sharing interface with live listing
- `GET /api/files/` — file listing partial
- `POST /api/upload/` — multipart upload with relative folder paths
- `GET /api/clipboard/` — list shared clipboard entries
- `POST /api/clipboard/add/` — append a text entry
- `POST /api/clipboard/<id>/delete/` — delete one clipboard entry
- `POST /api/clipboard/clear/` — delete all clipboard entries
- `GET /files/<path>` — download a shared file

Clipboard entries are stored transactionally in the Django database and
included in the app's migrations. Clipboard history is limited to 100 entries
and 10 MB. All files and clipboard entries follow the same local-network
privacy model.

Storage paths are logical paths handled by the configured
`STORAGES["vaalboks"]` backend. The backend must implement `listdir()` and
`size()` for browser listings.
