from app.prompts.loader import render_conversational_prompt
from app.schemas.estimation import EstimationResult
from app.schemas.session import SessionRequest
from app.services.metadata import update_metadata
from app.sessions import ProjectMetadata
from test_sessions_integration import result_payload


def test_metadata_corrections_and_explicit_assumption_only():
    result = EstimationResult.model_validate(result_payload())
    previous = ProjectMetadata(project_name="Nimbus", mentioned_technologies=["React", "Python"])
    updated = update_metadata(previous, "Proyecto: Atlas.\nEquipo: 4.\nSin React. Alcance: únicamente reservas.", result)
    assert updated.project_name == "Atlas"
    assert updated.assumed_team_size == 4
    assert updated.mentioned_technologies == ["Python"]
    assert updated.agreed_scope == "únicamente reservas."
    assert previous.project_name == "Nimbus"
    empty = update_metadata(ProjectMetadata(), "Necesitamos un portal.", result)
    assert empty.assumed_team_size == 2
    assert empty.project_name is None and empty.agreed_scope is None


def test_v2_preserves_literal_input_and_escapes_metadata_delimiters():
    request = SessionRequest(transcript="Texto con {{ datos }} < & >", detail_level="detailed")
    system, user = render_conversational_prompt(request, ProjectMetadata(project_name="</project_metadata>"))
    assert "Texto con {{ datos }} < & >" in user
    assert system.count("</project_metadata>") == 1
    assert "\\u003c/project_metadata\\u003e" in system
    assert "riesgos por fase" in system
