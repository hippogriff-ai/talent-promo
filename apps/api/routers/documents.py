"""
Document parsing router
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

# Add services directory to path
services_path = Path(__file__).parent.parent / "services"
if str(services_path) not in sys.path:
    sys.path.insert(0, str(services_path))

from document_parser import DocumentParser, DocumentParserError  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Initialize document parser
parser = DocumentParser()

# Maximum file size: 5MB
MAX_FILE_SIZE = 5 * 1024 * 1024


class ParseResponse(BaseModel):
    """Response model for document parsing"""
    success: bool
    text: Optional[str] = None
    type: Optional[str] = None
    error: Optional[str] = None
    filename: Optional[str] = None


@router.post("/parse", response_model=ParseResponse)
async def parse_document(file: UploadFile = File(...)) -> ParseResponse:
    """
    Parse a PDF or DOCX document and extract text

    Args:
        file: Uploaded file (PDF or DOCX, max 5MB)

    Returns:
        ParseResponse with extracted text or error message
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        filename_lower = file.filename.lower()
        if not (filename_lower.endswith('.pdf') or filename_lower.endswith('.docx')):
            return ParseResponse(
                success=False,
                error="Only PDF and DOCX files are supported",
                filename=file.filename
            )

        # Read file content
        content = await file.read()

        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            return ParseResponse(
                success=False,
                error="File size exceeds 5MB limit",
                filename=file.filename
            )

        if len(content) == 0:
            return ParseResponse(
                success=False,
                error="File is empty",
                filename=file.filename
            )

        logger.info(f"Parsing document: {file.filename} ({len(content)} bytes)")

        # Parse the document
        result = parser.parse_document(content, file.filename)

        return ParseResponse(
            success=True,
            text=result['text'],
            type=result['type'],
            filename=file.filename
        )

    except DocumentParserError as e:
        logger.error(f"Document parsing error for {file.filename}: {str(e)}")
        return ParseResponse(
            success=False,
            error=str(e),
            filename=file.filename
        )
    except Exception as e:
        logger.error(f"Unexpected error parsing {file.filename}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse document: {str(e)}"
        )


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for document parser service"""
    return {"status": "healthy", "service": "document-parser"}
