import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "app.db"
_UNSET = object()


def _ensure_parent_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    _ensure_parent_dir()
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS google_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_uri TEXT,
                client_id TEXT,
                client_secret TEXT,
                scopes TEXT,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id TEXT NOT NULL,
                name TEXT NOT NULL,
                emoji TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                error_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT,
                UNIQUE(folder_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pending_folder_id INTEGER,
                folder_id TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                file_id TEXT,
                file_name TEXT,
                data_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(folder_id, doc_type),
                FOREIGN KEY(pending_folder_id) REFERENCES pending_folders(id) ON DELETE SET NULL
            )
            """
        )
        _ensure_document_extractions_schema(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pending_folder_id INTEGER NOT NULL,
                folder_id TEXT NOT NULL,
                plus_value REAL,
                plus_value_details TEXT,
                evaluation_value REAL,
                evaluation_details TEXT,
                final_synthesis TEXT,
                final_doc_id TEXT,
                final_doc_link TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(pending_folder_id),
                FOREIGN KEY(pending_folder_id) REFERENCES pending_folders(id) ON DELETE CASCADE
            )
            """
        )
        _ensure_reports_schema(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processing_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pending_folder_id INTEGER NOT NULL,
                stage TEXT,
                doc_type TEXT,
                error_code TEXT,
                message TEXT NOT NULL,
                raw_payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(pending_folder_id) REFERENCES pending_folders(id) ON DELETE CASCADE
            )
            """
        )


def _ensure_document_extractions_schema(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(document_extractions)").fetchall()
    }
    if "pending_folder_id" not in columns:
        conn.execute(
            "ALTER TABLE document_extractions ADD COLUMN pending_folder_id INTEGER REFERENCES pending_folders(id) ON DELETE SET NULL"
        )


def _ensure_reports_schema(conn: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()
    }
    if "plus_value_details" not in columns:
        conn.execute(
            "ALTER TABLE reports ADD COLUMN plus_value_details TEXT"
        )
    if "evaluation_value" not in columns:
        conn.execute(
            "ALTER TABLE reports ADD COLUMN evaluation_value REAL"
        )
    if "evaluation_details" not in columns:
        conn.execute(
            "ALTER TABLE reports ADD COLUMN evaluation_details TEXT"
        )
    if "final_synthesis" not in columns:
        conn.execute(
            "ALTER TABLE reports ADD COLUMN final_synthesis TEXT"
        )
    if "final_doc_id" not in columns:
        conn.execute(
            "ALTER TABLE reports ADD COLUMN final_doc_id TEXT"
        )
    if "final_doc_link" not in columns:
        conn.execute(
            "ALTER TABLE reports ADD COLUMN final_doc_link TEXT"
        )


def clear_tokens() -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM google_tokens")


def save_credentials(
    *,
    access_token: str,
    refresh_token: Optional[str],
    token_uri: Optional[str],
    client_id: Optional[str],
    client_secret: Optional[str],
    scopes: Iterable[str],
    expires_at: Optional[str],
) -> None:
    init_db()
    scope_str = ",".join(sorted(set(scopes)))
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO google_tokens (
                access_token,
                refresh_token,
                token_uri,
                client_id,
                client_secret,
                scopes,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                access_token,
                refresh_token,
                token_uri,
                client_id,
                client_secret,
                scope_str,
                expires_at,
            ),
        )


def get_latest_token() -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT *
            FROM google_tokens
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    return row


def enqueue_pending_folder(*, folder_id: str, name: str, emoji: str) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pending_folders (
                folder_id,
                name,
                emoji,
                status
            )
            VALUES (?, ?, ?, 'queued')
            ON CONFLICT(folder_id) DO UPDATE SET
                name=excluded.name,
                emoji=excluded.emoji,
                status='queued',
                error_reason=NULL,
                updated_at=CURRENT_TIMESTAMP,
                processed_at=NULL
            """,
            (folder_id, name, emoji),
        )


def get_pending_folders(status: Optional[str] = None) -> List[sqlite3.Row]:
    init_db()
    query = "SELECT * FROM pending_folders"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at ASC"
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return rows


def update_pending_status(
    *, folder_id: str, status: str, error_reason: Optional[str] = None
) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE pending_folders
            SET status = ?,
                error_reason = ?,
                updated_at = CURRENT_TIMESTAMP,
                processed_at = CASE
                    WHEN ? = 'done' THEN CURRENT_TIMESTAMP
                    WHEN ? IN ('queued', 'processing') THEN NULL
                    ELSE processed_at
                END
            WHERE folder_id = ?
            """,
            (status, error_reason, status, status, folder_id),
        )


def save_document_extraction(
    *,
    pending_folder_id: Optional[int],
    folder_id: str,
    doc_type: str,
    file_id: Optional[str],
    file_name: Optional[str],
    data: dict,
) -> None:
    init_db()
    payload = json.dumps(data, ensure_ascii=False)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO document_extractions (
                pending_folder_id,
                folder_id,
                doc_type,
                file_id,
                file_name,
                data_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(folder_id, doc_type) DO UPDATE SET
                pending_folder_id=excluded.pending_folder_id,
                file_id=excluded.file_id,
                file_name=excluded.file_name,
                data_json=excluded.data_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                pending_folder_id,
                folder_id,
                doc_type,
                file_id,
                file_name,
                payload,
            ),
        )


def get_document_extraction(*, folder_id: str, doc_type: str) -> Optional[sqlite3.Row]:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT *
            FROM document_extractions
            WHERE folder_id = ? AND doc_type = ?
            """,
            (folder_id, doc_type),
        ).fetchone()
    return row


def list_document_extractions(
    *, folder_id: Optional[str] = None, pending_folder_id: Optional[int] = None
) -> List[sqlite3.Row]:
    init_db()
    query = "SELECT * FROM document_extractions"
    clauses = []
    params: List[object] = []
    if folder_id:
        clauses.append("folder_id = ?")
        params.append(folder_id)
    if pending_folder_id is not None:
        clauses.append("pending_folder_id = ?")
        params.append(pending_folder_id)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return rows


def get_job_stats() -> dict:
    """
    Retourne des statistiques agrégées sur les jobs (par statut et dernières mises à jour).
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        total = cursor.execute("SELECT COUNT(*) FROM pending_folders").fetchone()[0]
        by_status = {
            row[0] or "unknown": row[1]
            for row in cursor.execute(
                "SELECT status, COUNT(*) FROM pending_folders GROUP BY status"
            ).fetchall()
        }
        last_update = cursor.execute(
            "SELECT MAX(updated_at) FROM pending_folders"
        ).fetchone()[0]

    return {
        "total": total,
        "queued": by_status.get("queued", 0),
        "processing": by_status.get("processing", 0),
        "done": by_status.get("done", 0),
        "error": by_status.get("error", 0),
        "last_update": last_update,
    }


def list_jobs_with_extractions() -> List[dict]:
    """
    Retourne toutes les entrées pending_folders et leurs documents extraits associés.
    """
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        jobs = conn.execute(
            "SELECT * FROM pending_folders ORDER BY created_at DESC"
        ).fetchall()
        if not jobs:
            return []

        folder_to_job_id = {job["folder_id"]: job["id"] for job in jobs}
        docs = conn.execute(
            "SELECT * FROM document_extractions ORDER BY created_at DESC"
        ).fetchall()
        reports = conn.execute(
            "SELECT * FROM reports ORDER BY created_at DESC"
        ).fetchall()

    doc_map: dict[int, List[dict]] = {job["id"]: [] for job in jobs}
    for doc in docs:
        target_id = doc["pending_folder_id"] or folder_to_job_id.get(doc["folder_id"])
        if target_id is None:
            continue
        doc_dict = dict(doc)
        payload = doc_dict.get("data_json")
        try:
            doc_dict["data"] = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            doc_dict["data"] = None
        doc_map.setdefault(target_id, []).append(doc_dict)

    report_map: dict[int, dict] = {}
    for report in reports:
        report_dict = dict(report)
        plus_payload = report_dict.get("plus_value_details")
        try:
            report_dict["plus_value_details"] = (
                json.loads(plus_payload) if plus_payload else None
            )
        except json.JSONDecodeError:
            report_dict["plus_value_details"] = None

        eval_payload = report_dict.get("evaluation_details")
        try:
            report_dict["evaluation_details"] = (
                json.loads(eval_payload) if eval_payload else None
            )
        except json.JSONDecodeError:
            report_dict["evaluation_details"] = None

        synth_payload = report_dict.get("final_synthesis")
        try:
            report_dict["final_synthesis"] = (
                json.loads(synth_payload) if synth_payload else None
            )
        except json.JSONDecodeError:
            report_dict["final_synthesis"] = synth_payload

        report_map[report["pending_folder_id"]] = report_dict

    result = []
    for job in jobs:
        result.append(
            {
                "job": dict(job),
                "documents": doc_map.get(job["id"], []),
                "report": report_map.get(job["id"]),
            }
        )
    return result


def get_job_with_details(folder_id: str) -> Optional[dict]:
    """
    Retourne une job unique avec ses documents et rapport associés.
    """
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        job = conn.execute(
            "SELECT * FROM pending_folders WHERE folder_id = ?", (folder_id,)
        ).fetchone()
        if job is None:
            return None
        docs = conn.execute(
            """
            SELECT *
            FROM document_extractions
            WHERE folder_id = ?
            ORDER BY created_at DESC
            """,
            (folder_id,),
        ).fetchall()
        report = conn.execute(
            "SELECT * FROM reports WHERE pending_folder_id = ?", (job["id"],)
        ).fetchone()
        errors = conn.execute(
            """
            SELECT *
            FROM processing_errors
            WHERE pending_folder_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (job["id"],),
        ).fetchall()

    doc_entries: List[dict] = []
    for doc in docs:
        doc_dict = dict(doc)
        payload = doc_dict.get("data_json")
        try:
            doc_dict["data"] = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            doc_dict["data"] = None
        doc_entries.append(doc_dict)

    report_dict: Optional[dict] = None
    if report:
        report_dict = dict(report)
        plus_payload = report_dict.get("plus_value_details")
        try:
            report_dict["plus_value_details"] = (
                json.loads(plus_payload) if plus_payload else None
            )
        except json.JSONDecodeError:
            report_dict["plus_value_details"] = None

        eval_payload = report_dict.get("evaluation_details")
        try:
            report_dict["evaluation_details"] = (
                json.loads(eval_payload) if eval_payload else None
            )
        except json.JSONDecodeError:
            report_dict["evaluation_details"] = None

        synth_payload = report_dict.get("final_synthesis")
        try:
            report_dict["final_synthesis"] = (
                json.loads(synth_payload) if synth_payload else None
            )
        except json.JSONDecodeError:
            report_dict["final_synthesis"] = synth_payload

    return {
        "job": dict(job),
        "documents": doc_entries,
        "report": report_dict,
        "errors": [dict(row) for row in errors],
    }


def save_report_entry(
    *,
    pending_folder_id: int,
    folder_id: str,
    plus_value=_UNSET,
    plus_value_details=_UNSET,
    evaluation_value=_UNSET,
    evaluation_details=_UNSET,
    final_synthesis=_UNSET,
    final_doc_id=_UNSET,
    final_doc_link=_UNSET,
) -> None:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            """
            SELECT plus_value,
                   plus_value_details,
                   evaluation_value,
                   evaluation_details,
                   final_synthesis,
                   final_doc_id,
                   final_doc_link
            FROM reports
            WHERE pending_folder_id = ?
            """,
            (pending_folder_id,),
        ).fetchone()

        def resolve_value(new_value, key):
            if new_value is _UNSET:
                return existing[key] if existing else None
            return new_value

        def resolve_details(new_value, key):
            if new_value is _UNSET:
                return existing[key] if existing else None
            if new_value is None:
                return None
            return json.dumps(new_value, ensure_ascii=False)

        plus_val = resolve_value(plus_value, "plus_value")
        plus_details = resolve_details(plus_value_details, "plus_value_details")
        eval_val = resolve_value(evaluation_value, "evaluation_value")
        eval_details = resolve_details(evaluation_details, "evaluation_details")
        synth_text = resolve_value(final_synthesis, "final_synthesis")
        doc_id = resolve_value(final_doc_id, "final_doc_id")
        doc_link = resolve_value(final_doc_link, "final_doc_link")

        conn.execute(
            """
            INSERT INTO reports (
                pending_folder_id,
                folder_id,
                plus_value,
                plus_value_details,
                evaluation_value,
                evaluation_details,
                final_synthesis,
                final_doc_id,
                final_doc_link
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pending_folder_id) DO UPDATE SET
                folder_id=excluded.folder_id,
                plus_value=excluded.plus_value,
                plus_value_details=excluded.plus_value_details,
                evaluation_value=excluded.evaluation_value,
                evaluation_details=excluded.evaluation_details,
                final_synthesis=excluded.final_synthesis,
                final_doc_id=excluded.final_doc_id,
                final_doc_link=excluded.final_doc_link,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                pending_folder_id,
                folder_id,
                plus_val,
                plus_details,
                eval_val,
                eval_details,
                synth_text,
                doc_id,
                doc_link,
            ),
        )


def get_report(pending_folder_id: int) -> Optional[sqlite3.Row]:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM reports WHERE pending_folder_id = ?", (pending_folder_id,)
        ).fetchone()
    return row


def clear_processing_errors(pending_folder_id: int) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM processing_errors WHERE pending_folder_id = ?",
            (pending_folder_id,),
        )


def log_processing_error(
    *,
    pending_folder_id: int,
    stage: Optional[str],
    doc_type: Optional[str],
    error_code: Optional[str],
    message: str,
    raw_payload: Optional[str] = None,
) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO processing_errors (
                pending_folder_id,
                stage,
                doc_type,
                error_code,
                message,
                raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                pending_folder_id,
                stage,
                doc_type,
                error_code,
                message,
                raw_payload,
            ),
        )


def list_processing_errors(pending_folder_id: int) -> List[sqlite3.Row]:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT *
            FROM processing_errors
            WHERE pending_folder_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (pending_folder_id,),
        ).fetchall()
    return rows
