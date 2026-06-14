"""
tests/test_pdf_service.py
==========================
Tests for PdfService — currently focused on _load_company(), which reads
saved company / quote settings from the ``settings`` table so generated
PDFs and text receipts reflect what the user configured in the Settings
tab (rather than always falling back to the hardcoded COMPANY dict).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config import COMPANY
from src.core.database import DatabaseManager
from src.services.pdf_service import PdfService


@pytest.fixture
def db():
    return DatabaseManager(":memory:")


class TestLoadCompany:

    def test_defaults_when_no_db(self):
        """db=None -> always fall back to config defaults."""
        svc = PdfService(db=None)
        company = svc._load_company()
        assert company["name"]    == COMPANY["name"]
        assert company["phone"]   == COMPANY["phone"]
        assert company["address"] == COMPANY["address"]
        assert company["deposit_pct"]   == 50
        assert company["validity_days"] == 7

    def test_defaults_when_no_settings_saved(self, db):
        """Fresh DB with no company_* settings -> config defaults."""
        svc = PdfService(db)
        company = svc._load_company()
        assert company["name"]  == COMPANY["name"]
        assert company["phone"] == COMPANY["phone"]

    def test_reads_saved_company_info(self, db):
        """Settings saved via the Settings tab should appear on PDFs."""
        db.save_all_settings({
            "company_name":        "Acme 3D Printing",
            "company_subtitle":    "Custom Prints",
            "company_phone":       "0123456789",
            "company_address":     "Cairo, Egypt",
            "company_tagline":     "Print it your way",
            "company_social":      "@acme3d",
            "quote_deposit_pct":   "40",
            "quote_validity_days": "14",
            "invoice_footer":      "See you again soon!",
        })
        svc = PdfService(db)
        company = svc._load_company()
        assert company["name"]          == "Acme 3D Printing"
        assert company["subtitle"]      == "Custom Prints"
        assert company["phone"]         == "0123456789"
        assert company["address"]       == "Cairo, Egypt"
        assert company["tagline"]       == "Print it your way"
        assert company["social"]        == "@acme3d"
        assert company["deposit_pct"]   == pytest.approx(40.0)
        assert company["validity_days"] == 14
        assert company["footer_note"]   == "See you again soon!"

    def test_partial_settings_fall_back_for_missing_keys(self, db):
        """Only some settings saved -> the rest keep config defaults."""
        db.save_setting("company_name", "Only Name Set")
        svc = PdfService(db)
        company = svc._load_company()
        assert company["name"]  == "Only Name Set"
        assert company["phone"] == COMPANY["phone"]
        assert company["deposit_pct"] == 50
