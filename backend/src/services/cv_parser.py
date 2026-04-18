from __future__ import annotations

import re
import tempfile
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from services.s3 import download_file


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
        return _strip_pii(text=markdown)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()
