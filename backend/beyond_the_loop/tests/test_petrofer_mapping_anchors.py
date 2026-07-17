"""
Hand-verified anchor tests for the generated Petrofer email→group mapping.

If any of these assertions fails, the mapping was regenerated incorrectly
(e.g. wrong CSV, wrong DB export, changed group UUIDs) and users would
land in the wrong groups on signup. This file exists purely as a
safety net against silent data drift.

Add a new anchor here every time you spot-check a real user manually.

Run with:
    cd backend
    pytest beyond_the_loop/tests/test_petrofer_mapping_anchors.py -v
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


def _stub_module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


_stub_module(
    "open_webui.internal.db",
    get_db=MagicMock(),
    Base=type("Base", (), {"metadata": MagicMock()}),
)
_stub_module("open_webui.env", SRC_LOG_LEVELS={"MODELS": "INFO"})


# --- Known-good DB group IDs (from studio_results_20260717_1444.csv) --------
GID_CEO = "a40025e4-179e-49a7-821a-0d0249119748"                # Geschäftsführung CEO
GID_LEITUNG_CEO = "975e8d9a-7a31-4bcd-b4a7-7c1a230a4299"        # Leitung Geschäftsführung CEO
GID_CFO = "ca8a0340-baac-4da5-90ea-b96cf8e820a0"                # Geschäftsführung CFO
GID_LEITUNG_CFO = "86549184-0c24-4fb8-80b4-f317515a90de"        # Leitung Geschäftsführung CFO
GID_COO_MW = "bf0cf044-8ab8-4e12-a758-88518b95d694"             # Geschäftsführung (COO) Metalworking Europe
GID_LEITUNG_COO_MW = "e8982280-291a-4913-a86e-fe4a5adf5c1a"     # Leitung Geschäftsführung (COO) Metalworking Europe
GID_STRATEGIE = "e4a81f2b-7e38-4081-b163-1b3f7bc6db53"          # Geschäftsführung Strategie
GID_LEITUNG_STRATEGIE = "bcd5573f-5e3a-4eb0-b51a-2119e595122f"  # Leitung Geschäftsführung Strategie
GID_VERTRIEB_ME = "03012285-b5d5-46a3-ac70-559676c24d7c"        # Vertrieb Metalworking Europe
GID_LEITUNG_VERTRIEB_ME = "2ce5e832-9292-424b-bc96-a6c3f29767f9"  # Leitung Vertrieb Metalworking Europe
GID_PRODUKTION = "c7ce1b6b-05fb-4305-9d96-a2e91c65f25a"         # Produktion
GID_LEITUNG_PRODUKTION = "93cc8469-2dee-4f64-a707-43a579d0f310"  # Leitung Produktion
GID_PRODUKTION_LOGISTIK = "2900fbdf-1db3-490d-a243-afc847cb3ca2"  # Produktion und Logistik
GID_HR = "8b55cade-3b3d-4a17-8422-65c08fe085e7"                 # Personalmanagement


def test_ceo_is_in_ceo_and_leitung_ceo():
    from beyond_the_loop.data.petrofer_group_assignments import EMAIL_TO_GROUP_IDS
    assert set(EMAIL_TO_GROUP_IDS["constantin.fischer@petrofer.com"]) == {
        GID_CEO,
        GID_LEITUNG_CEO,
    }


def test_cfo_is_in_cfo_and_leitung_cfo():
    from beyond_the_loop.data.petrofer_group_assignments import EMAIL_TO_GROUP_IDS
    assert set(EMAIL_TO_GROUP_IDS["michael.scheibner@petrofer.com"]) == {
        GID_CFO,
        GID_LEITUNG_CFO,
    }


def test_coo_metalworking_is_in_coo_and_leitung_coo():
    from beyond_the_loop.data.petrofer_group_assignments import EMAIL_TO_GROUP_IDS
    assert set(EMAIL_TO_GROUP_IDS["nebojsa.obradovic@petrofer.com"]) == {
        GID_COO_MW,
        GID_LEITUNG_COO_MW,
    }


def test_leitung_strategie():
    from beyond_the_loop.data.petrofer_group_assignments import EMAIL_TO_GROUP_IDS
    assert set(EMAIL_TO_GROUP_IDS["gesa-marie.fischer@petrofer.com"]) == {
        GID_STRATEGIE,
        GID_LEITUNG_STRATEGIE,
    }


def test_leitung_vertrieb_metalworking():
    from beyond_the_loop.data.petrofer_group_assignments import EMAIL_TO_GROUP_IDS
    assert set(EMAIL_TO_GROUP_IDS["christian.holzminden@petrofer.com"]) == {
        GID_COO_MW,
        GID_VERTRIEB_ME,
        GID_LEITUNG_VERTRIEB_ME,
    }


def test_leitung_produktion_multi_department():
    """Patrick Kutzler leads Produktion; sits in CEO, PL, PR, Leitung PR."""
    from beyond_the_loop.data.petrofer_group_assignments import EMAIL_TO_GROUP_IDS
    assert set(EMAIL_TO_GROUP_IDS["patrick.kutzler@petrofer.com"]) == {
        GID_CEO,
        GID_PRODUKTION_LOGISTIK,
        GID_PRODUKTION,
        GID_LEITUNG_PRODUKTION,
    }


def test_hr_membership():
    """Anja Schubert is in CEO + Personalmanagement (HR)."""
    from beyond_the_loop.data.petrofer_group_assignments import EMAIL_TO_GROUP_IDS
    assert set(EMAIL_TO_GROUP_IDS["anja.schubert@petrofer.com"]) == {
        GID_CEO,
        GID_HR,
    }


def test_no_duplicate_group_ids_per_email():
    """No email should list the same group ID twice."""
    from beyond_the_loop.data.petrofer_group_assignments import EMAIL_TO_GROUP_IDS
    for email, gids in EMAIL_TO_GROUP_IDS.items():
        assert len(gids) == len(set(gids)), f"Duplicate group ids for {email}"


def test_company_id_is_the_pinned_petrofer_id():
    """The hardcoded company id must never accidentally change."""
    from beyond_the_loop.data.petrofer_group_assignments import PETROFER_COMPANY_ID
    assert PETROFER_COMPANY_ID == "383e3338-9883-4b3e-8dd6-d32f9a58339f"


def test_qa_test_email_has_ten_groups():
    """phil+testpetrofer@beyondtheloop.ai must be mapped to exactly 10 groups
    (deterministic seed=42 in the generator)."""
    from beyond_the_loop.data.petrofer_group_assignments import EMAIL_TO_GROUP_IDS
    assert len(EMAIL_TO_GROUP_IDS["phil+testpetrofer@beyondtheloop.ai"]) == 10
