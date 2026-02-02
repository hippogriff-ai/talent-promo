"""Tests for the document parsing endpoint."""
import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestDocumentParseEndpoint:
    """Test POST /api/documents/parse"""

    def test_rejects_unsupported_file_type(self):
        """TXT files should be rejected"""
        file = io.BytesIO(b"plain text content")
        response = client.post(
            "/api/documents/parse",
            files={"file": ("resume.txt", file, "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "only pdf and docx" in data["error"].lower()

    def test_rejects_empty_file(self):
        """Empty files should be rejected"""
        file = io.BytesIO(b"")
        response = client.post(
            "/api/documents/parse",
            files={"file": ("resume.pdf", file, "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "empty" in data["error"].lower()

    def test_rejects_oversized_file(self):
        """Files over 5MB should be rejected"""
        file = io.BytesIO(b"x" * (5 * 1024 * 1024 + 1))
        response = client.post(
            "/api/documents/parse",
            files={"file": ("resume.pdf", file, "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "5mb" in data["error"].lower()

    @patch("routers.documents.parser")
    def test_successful_pdf_parse(self, mock_parser):
        """Valid PDF should return extracted text"""
        mock_parser.parse_document.return_value = {
            "text": "John Doe\nSoftware Engineer\n5 years experience",
            "type": "pdf",
        }
        file = io.BytesIO(b"%PDF-1.4 fake pdf content")
        response = client.post(
            "/api/documents/parse",
            files={"file": ("resume.pdf", file, "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "John Doe" in data["text"]
        assert data["type"] == "pdf"
        assert data["filename"] == "resume.pdf"

    @patch("routers.documents.parser")
    def test_successful_docx_parse(self, mock_parser):
        """Valid DOCX should return extracted text"""
        mock_parser.parse_document.return_value = {
            "text": "Jane Smith\nProduct Manager\nLed team of 12",
            "type": "docx",
        }
        file = io.BytesIO(b"PK\x03\x04 fake docx content")
        response = client.post(
            "/api/documents/parse",
            files={"file": ("resume.docx", file, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Jane Smith" in data["text"]
        assert data["type"] == "docx"

    @patch("routers.documents.parser")
    def test_parser_error_handled(self, mock_parser):
        """DocumentParserError should return error response, not 500"""
        from document_parser import DocumentParserError
        mock_parser.parse_document.side_effect = DocumentParserError("Corrupt PDF")
        file = io.BytesIO(b"%PDF corrupt")
        response = client.post(
            "/api/documents/parse",
            files={"file": ("bad.pdf", file, "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Corrupt PDF" in data["error"]

    def test_health_endpoint(self):
        """Health check should return healthy"""
        response = client.get("/api/documents/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_accepts_pdf_extension_case_insensitive(self):
        """Should accept .PDF uppercase extension"""
        file = io.BytesIO(b"")  # Will fail on empty, but validates extension first
        response = client.post(
            "/api/documents/parse",
            files={"file": ("resume.PDF", file, "application/pdf")},
        )
        data = response.json()
        # Should get past extension check (fail on empty, not on type)
        assert data["success"] is False
        assert "empty" in data["error"].lower()
