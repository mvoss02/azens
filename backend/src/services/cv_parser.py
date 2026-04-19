from __future__ import annotations

import asyncio
import logging
import re
import tempfile
import time
import uuid
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from sqlalchemy import select

from core.database import SessionLocal
from models.cv import CV
from models.enums import CVParsingStatus
from services.s3 import download_file

logger = logging.getLogger(__name__)

# parsing_error is exposed to the UI via CVResponse — trim so we don't leak
# a full Docling stack trace to the browser. Full detail stays in logs.
_PARSE_ERROR_MAX_CHARS = 500


def _build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()

    # Good defaults for SaaS ingestion:
    pipeline_options.do_ocr = True  # helps with scanned PDFs
    pipeline_options.do_table_structure = True  # preserve tables
    pipeline_options.table_structure_options = TableStructureOptions(
        do_cell_matching=True
    )

    return DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        },
    )


# Module level — built once:
_converter = _build_converter()


def _strip_pii(text: str) -> str:
    # Email addresses
    text = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[EMAIL]', text)
    # Phone numbers (various formats)
    text = re.sub(r'[\+]?[(]?[0-9]{1,4}[)]?[-\s./0-9]{7,15}', '[PHONE]', text)
    # Street addresses (basic — catches "123 Main St" patterns)
    text = re.sub(
        r'\d{1,5}\s+[\w\s]{1,30}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct)\.?',
        '[ADDRESS]',
        text,
        flags=re.IGNORECASE,
    )

    return text


def parse_cv_from_s3(s3_key: str) -> str:
    start = time.monotonic()
    logger.info('cv_parse_start s3_key=%s', s3_key)

    # 1. Download from S3
    file = download_file(s3_key=s3_key)

    # 2. Write to temp file
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(file)
            tmp_path = Path(tmp.name)

        # 3. Convert with docling
        result = _converter.convert(str(tmp_path))
        markdown = result.document.export_to_markdown()

        # 4. Return cleaned text
        cleaned = _strip_pii(text=markdown)

        logger.info(
            'cv_parse_done s3_key=%s duration_s=%.2f chars=%d',
            s3_key,
            time.monotonic() - start,
            len(cleaned),
        )

        return cleaned
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


async def parse_cv_background(cv_id: uuid.UUID, s3_key: str) -> None:
    """Parse a CV in a FastAPI BackgroundTask, persist result + status.

    Runs with its OWN async DB session because the request's session was
    closed the moment the /confirm response went out. We deliberately do the
    blocking Docling work *outside* the DB session — parsing can take tens of
    seconds and we don't want to hold a connection the whole time.
    """
    parsed_text: str | None = None
    error_msg: str | None = None

    try:
        parsed_text = await asyncio.to_thread(parse_cv_from_s3, s3_key)
    except Exception as exc:
        # Full exception + traceback goes to the log; the user-facing message
        # is the repr, truncated.
        logger.exception('cv_parse_failed cv_id=%s s3_key=%s', cv_id, s3_key)
        error_msg = repr(exc)[:_PARSE_ERROR_MAX_CHARS]

    async with SessionLocal() as session:
        result = await session.execute(select(CV).where(CV.id == cv_id))
        cv = result.scalar_one_or_none()
        if cv is None:
            # User deleted the CV while it was being parsed. Nothing to do.
            logger.info('cv_parse_orphan cv_id=%s (row gone)', cv_id)
            return

        if parsed_text is not None:
            cv.parsed_text = parsed_text
            cv.parsing_status = CVParsingStatus.PARSED
            cv.parsing_error = None
        else:
            cv.parsing_status = CVParsingStatus.FAILED
            cv.parsing_error = error_msg

        await session.commit()
