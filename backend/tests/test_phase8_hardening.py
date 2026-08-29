"""Phase 8 regression checks for truthful degradation and plan lineage."""

from backend.agents.disaster_intelligence import SPECIALIST_AGENTS
from backend.database.models import AgentRunDB
from backend.services.disaster_intelligence_service import trigger_disaster_intelligence


def test_optional_specialist_failure_is_visible_without_aborting_workflow(db_session, monkeypatch):
    def unavailable(_state):
        raise RuntimeError("weather provider unavailable")

    monkeypatch.setattr(SPECIALIST_AGENTS["weather_analysis"], "analyze", unavailable)

    result = trigger_disaster_intelligence(
        db_session,
        source="sensor",
        location="Nepal Mountain N-14",
        description="Rainfall and ground movement anomalies indicate landslide risk.",
        zone_id="DEMO-N14",
        disaster_type="landslide",
    )

    assert any(error.startswith("weather_analysis:") for error in result["agent_errors"])
    assert "weather_analysis" not in result["agent_results"]
    assert "geo_vulnerability" in result["agent_results"]
    assert result["response_plan"]["approval_status"] == "pending"
    run = db_session.query(AgentRunDB).filter_by(run_id=result["agent_run_id"]).one()
    assert run.status == "completed_with_errors"
