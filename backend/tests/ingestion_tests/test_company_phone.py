"""Tests for company contact phone validation."""

import pytest
from pydantic import ValidationError

from src.api.v1.schemas.ingestion import CompanyCreateRequest


def test_company_create_request_normalizes_phone() -> None:
    """Readable international phone values are normalized before storage."""
    body = CompanyCreateRequest(
        name="DRC Women Peacebuilders",
        email="support@example.org",
        phone="+254 712-345-678",
    )
    assert body.phone == "+254712345678"


def test_company_create_request_allows_missing_phone() -> None:
    """Phone is optional while the table column remains nullable."""
    body = CompanyCreateRequest(
        name="DRC Women Peacebuilders",
        email="support@example.org",
    )
    assert body.phone is None


def test_company_create_request_rejects_invalid_phone() -> None:
    """Invalid phone values are rejected by request validation."""
    with pytest.raises(ValidationError):
        CompanyCreateRequest(
            name="DRC Women Peacebuilders",
            email="support@example.org",
            phone="123",
        )
