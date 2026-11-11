"""Extracción local de PDF y DOCX en memoria, sin guardar archivos del usuario."""

from io import BytesIO
from pathlib import PurePosixPath
import re
from zipfile import ZipFile

from docx import Document
from docx.table import Table
from pypdf import PdfReader


class AttachmentError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.public_message = message
        super().__init__(message)


def safe_filename(filename: str) -> str:
    name = PurePosixPath(filename.replace("\\", "/")).name
    return re.sub(r"[^\w. -]", "_", name)[:120] or "adjunto"


def extract_text(filename: str, content: bytes, max_chars: int) -> str:
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in {".pdf", ".docx"}:
        raise AttachmentError(415, "Solo se admiten PDF con texto y documentos Word .docx.")
    try:
        if extension == ".pdf":
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise AttachmentError(422, "El PDF está protegido; adjunta una copia sin contraseña.")
            if len(reader.pages) > 200:
                raise AttachmentError(413, "El PDF supera el límite de 200 páginas.")
            blocks = (page.extract_text() or "" for page in reader.pages)
        else:
            with ZipFile(BytesIO(content)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 20_000_000:
                    raise AttachmentError(413, "El contenido descomprimido del Word es demasiado grande.")
            document = Document(BytesIO(content))
            blocks = (
                "\n".join(" | ".join(cell.text for cell in row.cells) for row in block.rows)
                if isinstance(block, Table) else block.text
                for block in document.iter_inner_content()
            )
        parts, size = [], 0
        for block in blocks:
            if block.strip():
                size += len(block) + (1 if parts else 0)
                if size > max_chars:
                    raise AttachmentError(413, "El texto del adjunto supera el límite; divide el documento.")
                parts.append(block)
        text = "\n".join(parts).strip()
        if not text:
            raise AttachmentError(422, "El adjunto no contiene texto extraíble. Los escaneos requieren OCR.")
        return text
    except AttachmentError:
        raise
    except Exception:
        raise AttachmentError(422, "No se pudo leer el adjunto; comprueba que sea un PDF o DOCX válido.") from None


def enrich_transcript(transcript: str, attachments: list[tuple[str, str]]) -> str:
    parts = [transcript]
    for filename, text in attachments:
        parts.append(f"--- attachment: {safe_filename(filename)} ---\n{text}\n--- end attachment ---")
    return "\n\n".join(parts)
