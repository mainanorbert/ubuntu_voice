"""Tests for incident-statistics classifier parsing and persistence."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.database import Base, create_database_engine, create_session_factory
from src.models import Company, IncidentStatistic, User
from src.services.incident_statistics import (
    IncidentClassifierOutput,
    IncidentStatisticRecord,
    parse_incident_classifier_json,
    sanitize_incident_description,
    upsert_incident_statistics,
)


def test_parse_incident_classifier_json_accepts_valid_output() -> None:
    """Valid strict JSON output becomes a typed classifier result."""
    output = parse_incident_classifier_json(
        """
        {
          "should_record": true,
          "records": [
            {
              "place": "Goma",
              "description": "Armed group violence reported near Goma.",
              "type": "Rights Violations"
            }
          ]
        }
        """
    )

    assert output.should_record is True
    assert output.records[0].place == "Goma"
    assert output.records[0].type == "Rights Violations"


@pytest.mark.parametrize(
    "raw_output",
    [
        "not json",
        '{"should_record": true, "records": [{"place": "Goma", "description": "Report", "type": "Other"}]}',
    ],
)
def test_parse_incident_classifier_json_rejects_malformed_or_unknown_types(raw_output: str) -> None:
    """Malformed JSON and unknown categories are rejected before persistence."""
    with pytest.raises(ValueError):
        parse_incident_classifier_json(raw_output)


def test_non_incident_classifier_output_stores_nothing() -> None:
    """Classifier output with should_record=false does not create rows."""
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        changed = upsert_incident_statistics(
            session,
            company_id="company_1",
            classifier_output=IncidentClassifierOutput(should_record=False, records=[]),
        )

        assert changed == []
        assert session.query(IncidentStatistic).count() == 0


def test_multi_record_upsert_creates_multiple_rows_and_increments_by_report() -> None:
    """Multiple records are stored and repeated place/type pairs increment by one."""
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        output = IncidentClassifierOutput(
            should_record=True,
            records=[
                IncidentStatisticRecord(
                    place="Goma",
                    description="12 casualties reported near Goma.",
                    type="Casualties",
                ),
                IncidentStatisticRecord(
                    place="Bukavu",
                    description="Severe hunger reported by displaced families.",
                    type="Severe Hunger",
                ),
            ],
        )
        upsert_incident_statistics(session, company_id="company_1", classifier_output=output)
        upsert_incident_statistics(
            session,
            company_id="company_1",
            classifier_output=IncidentClassifierOutput(
                should_record=True,
                records=[
                    IncidentStatisticRecord(
                        place="goma",
                        description="Another casualties report near Goma.",
                        type="Casualties",
                    )
                ],
            ),
        )

        rows = session.query(IncidentStatistic).order_by(IncidentStatistic.type.asc()).all()
        assert len(rows) == 2
        casualty_row = next(row for row in rows if row.type == "Casualties")
        hunger_row = next(row for row in rows if row.type == "Severe Hunger")
        assert casualty_row.total_count == 2
        assert casualty_row.normalized_place == "goma"
        assert hunger_row.total_count == 1


def test_upsert_retries_as_increment_when_concurrent_insert_wins(tmp_path, monkeypatch) -> None:
    """A unique-key race on first insert increments the winning row instead of losing the report."""
    engine = create_database_engine(f"sqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        original_commit = session.commit
        original_rollback = session.rollback
        commit_calls = 0
        rollback_calls = 0

        def flaky_first_commit() -> None:
            nonlocal commit_calls
            if commit_calls == 0:
                commit_calls += 1
                raise IntegrityError("insert incident statistic", {}, Exception("unique constraint"))
            original_commit()

        def insert_competing_row_on_first_rollback() -> None:
            nonlocal rollback_calls
            original_rollback()
            if rollback_calls == 0:
                rollback_calls += 1
                with factory() as competing_session:
                    competing_session.add(
                        IncidentStatistic(
                            id="competing_stat",
                            company_id="company_1",
                            place="Goma",
                            normalized_place="goma",
                            description="Competing casualties report near Goma.",
                            type="Casualties",
                            total_count=1,
                        )
                    )
                    competing_session.commit()

        monkeypatch.setattr(session, "commit", flaky_first_commit)
        monkeypatch.setattr(session, "rollback", insert_competing_row_on_first_rollback)

        changed = upsert_incident_statistics(
            session,
            company_id="company_1",
            classifier_output=IncidentClassifierOutput(
                should_record=True,
                records=[
                    IncidentStatisticRecord(
                        place="Goma",
                        description="Classifier casualties report near Goma.",
                        type="Casualties",
                    )
                ],
            ),
        )

        row = session.query(IncidentStatistic).one()
        assert changed[0].id == row.id
        assert row.total_count == 2
        assert row.description == "Classifier casualties report near Goma."


def test_sanitize_incident_description_removes_contact_details() -> None:
    """Stored summaries are defensively sanitized even after classifier output."""
    summary = sanitize_incident_description(
        "My name is Jane Doe. Armed actors arrived in Goma. Call +254 712-345-678 or jane@example.org."
    )

    assert "Jane Doe" not in summary
    assert "+254 712-345-678" not in summary
    assert "jane@example.org" not in summary
    assert "Goma" in summary


def test_incident_statistics_endpoint_returns_only_owned_company_rows(tmp_path, monkeypatch) -> None:
    """Statistics reads are scoped to companies owned by the authenticated user."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-clerk-secret")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / 'incident_stats.db'}")

    from src.core.dependencies import clear_database_caches, get_database_engine, get_settings

    clear_database_caches()

    from src.core.clerk_auth import require_clerk_session
    from src.main import app

    async def fake_require_clerk_session():
        return SimpleNamespace(payload={"sub": "owner_1", "email": "owner@example.org"})

    app.dependency_overrides[require_clerk_session] = fake_require_clerk_session

    try:
        settings = get_settings()
        engine = get_database_engine(settings.database_url)
        Base.metadata.create_all(bind=engine)
        with Session(engine) as session:
            session.add(User(id="owner_1", email="owner@example.org"))
            session.add(User(id="owner_2", email="other@example.org"))
            session.add(
                Company(
                    id="company_1",
                    name="DRC Women Peacebuilders",
                    email="agent@example.org",
                    owner_id="owner_1",
                )
            )
            session.add(
                Company(
                    id="company_2",
                    name="Other Agent",
                    email="other-agent@example.org",
                    owner_id="owner_2",
                )
            )
            session.add(
                IncidentStatistic(
                    id="stat_1",
                    company_id="company_1",
                    place="Goma",
                    normalized_place="goma",
                    description="Casualties reported near Goma.",
                    type="Casualties",
                    total_count=3,
                )
            )
            session.add(
                IncidentStatistic(
                    id="stat_2",
                    company_id="company_2",
                    place="Bukavu",
                    normalized_place="bukavu",
                    description="Displacement reported near Bukavu.",
                    type="Displacements",
                    total_count=8,
                )
            )
            session.commit()

        with TestClient(app) as client:
            response = client.get("/api/v1/monitoring/incident-statistics")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["company_id"] == "company_1"
        assert data[0]["company_name"] == "DRC Women Peacebuilders"
        assert data[0]["place"] == "Goma"
    finally:
        app.dependency_overrides.clear()
        clear_database_caches()
