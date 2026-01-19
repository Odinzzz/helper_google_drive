from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape


@dataclass(frozen=True)
class PdfResult:
    path: Path
    filename: str


def _safe_filename(value: str) -> str:
    sanitized = []
    for char in value.strip():
        if char.isalnum() or char in {"-", "_", "."}:
            sanitized.append(char)
        elif char.isspace():
            sanitized.append("_")
    return "".join(sanitized).strip("_") or "rapport"


def _extract_address(entry: dict) -> Optional[str]:
    documents = entry.get("documents") or []
    for doc in documents:
        if doc.get("doc_type") != "jlr":
            continue
        data = doc.get("data") or {}
        address = data.get("civic_address")
        if address:
            return str(address)
    return None


def render_job_report_pdf(
    *,
    entry: dict,
    folder_id: str,
    output_dir: Path,
    logo_uri: str,
    base_dir: Path,
) -> PdfResult:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on env
        raise RuntimeError(
            "WeasyPrint n'est pas disponible. Installez les dependances systeme puis "
            "`pip install weasyprint`."
        ) from exc

    job_name = entry.get("job", {}).get("name") or folder_id
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{_safe_filename(job_name)}_{timestamp}.pdf"

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / filename

    address = _extract_address(entry)
    balloon_uri = (base_dir / "static" / "images" / "remax_ballon.png").resolve().as_uri()
    secondary_logo_uri = (
        base_dir / "static" / "images" / "SSecondaire_Bleu.png"
    ).resolve().as_uri()
    icon_uri = (base_dir / "static" / "images" / "Icone_Bleu.png").resolve().as_uri()

    env = Environment(
        loader=FileSystemLoader(str(base_dir / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("reports/job_report.html")
    html = template.render(
        entry=entry,
        folder_id=folder_id,
        logo_uri=logo_uri,
        address=address,
        balloon_uri=balloon_uri,
        secondary_logo_uri=secondary_logo_uri,
        icon_uri=icon_uri,
    )
    HTML(string=html, base_url=str(base_dir)).write_pdf(str(pdf_path))

    return PdfResult(path=pdf_path, filename=filename)
