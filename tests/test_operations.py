from datetime import date

import pytest
from fastapi import HTTPException

from engine.collect_sec import candidates, identities
from engine.operations import exclusive_replay
from engine.serve import configure


def test_operator_replay_is_exclusive_and_released_on_failure():
    with pytest.raises(RuntimeError), exclusive_replay():
        with pytest.raises(HTTPException) as error, exclusive_replay():
            pytest.fail("Concurrent replay admitted")
        assert error.value.status_code == 409
        raise RuntimeError("Simulated worker failure")
    with exclusive_replay():
        pass


def test_database_secret_configuration(tmp_path, monkeypatch):
    path = tmp_path / "database-url"
    path.write_text("postgresql+psycopg://test:test@localhost/test\n")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL_FILE", str(path))
    configure()
    with pytest.raises(ValueError, match="not both"):
        configure()
    monkeypatch.delenv("DATABASE_URL")
    path.write_text("sqlite:///unapproved.db")
    with pytest.raises(ValueError, match="PostgreSQL"):
        configure()


def test_sec_identity_cross_checks():
    payload = {
        str(i): {"ticker": ticker, "cik_str": i + 1, "title": ticker}
        for i, ticker in enumerate(("MU", "NVDA", "AMD", "DELL", "SNDK"))
    }
    assert len(identities(payload)) == 5
    payload["4"]["cik_str"] = 1
    with pytest.raises(ValueError, match="distinct"):
        identities(payload)


def test_filing_candidates_preserve_real_capture_and_reject_wdc_substitution():
    payload = {
        "cik": "2023554",
        "tickers": ["SNDK"],
        "filings": {
            "recent": {
                "accessionNumber": ["0002023554-25-000001", "0002023554-25-000002"],
                "filingDate": ["2025-02-20", "2025-03-01"],
                "form": ["10-Q", "8-K"],
                "primaryDocument": ["test.htm", "test2.htm"],
            }
        },
    }
    result = candidates("SNDK", "0002023554", payload, date(2025, 1, 1), date(2025, 12, 31), 10)
    assert len(result) == 1
    assert result[0]["historical_as_of_eligible"] is False
    assert result[0]["rights_status"] == "pending_review"
    assert result[0]["canonical_event_key"] is None
    payload["tickers"] = ["WDC"]
    with pytest.raises(ValueError, match="disagrees"):
        candidates("SNDK", "0002023554", payload, date(2025, 1, 1), date(2025, 12, 31), 10)
