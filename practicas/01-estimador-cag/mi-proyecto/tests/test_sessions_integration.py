import asyncio
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

from docx import Document
import httpx
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
import pytest

from app.main import app
from app.routers.sessions import get_session_store
from app.schemas.estimation import EstimationResult
from app.services import conversation
from app.services.errors import LLMServiceError
from app.sessions import SessionStore


def result_payload(cost=1000):
    return {
        "summary": "Estimación orientativa del proyecto. Equipo asumido: 2.",
        "confidence_pct": 80,
        "phases": [{"name": "Construcción", "duration_weeks": 2,
                    "cost_eur": cost, "summary": "Construir y verificar los entregables acordados."}],
        "total_duration_weeks": 2, "total_cost_eur": cost,
    }


def pdf_bytes(text="INTEGRACION_SAP"):
    writer = PdfWriter()
    page = writer.add_blank_page(width=500, height=500)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)}),
    })
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 30 450 Td ({text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def docx_bytes():
    document = Document()
    document.add_paragraph("Proyecto: Nimbus.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Tecnologías"
    table.cell(0, 1).text = "Python y PostgreSQL"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.fixture
async def api(monkeypatch):
    calls = []
    store = SessionStore(max_turns=3)
    async def fake_generate(messages):
        calls.append(deepcopy(messages))
        await asyncio.sleep(0)
        cost = 2500 if "INTEGRACION_SAP" in messages[-1]["content"] else 1000
        return {"result": EstimationResult.model_validate(result_payload(cost))}
    monkeypatch.setattr(conversation, "generate_structured_estimation", fake_generate)
    app.dependency_overrides[get_session_store] = lambda: store
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield SimpleNamespace(client=client, calls=calls, store=store)
    finally:
        app.dependency_overrides.pop(get_session_store, None)


async def create(api):
    response = await api.client.post("/sessions")
    assert response.status_code == 201
    return response.json()["session_id"]


async def estimate(api, session_id, transcript, uploads=(), **options):
    files = [(name, (None, value)) for name, value in {"transcript": transcript, **options}.items()]
    files.extend(("attachments", upload) for upload in uploads)
    return await api.client.post(f"/sessions/{session_id}/estimate", files=files)


async def test_two_turns_accumulate_metadata_and_regenerate_system(api):
    session_id = await create(api)
    first = await estimate(api, session_id, "Proyecto: Nimbus.\nEquipo: 3.\nAlcance: reservar salas.\nPython y React.")
    assert first.status_code == 200, first.text
    assert "<project_metadata></project_metadata>" in api.calls[0][0]["content"]
    second = await estimate(api, session_id, "Equipo: 5.\nAñade calendario y Stripe.")
    assert second.status_code == 200, second.text
    facts = second.json()["project_metadata"]
    assert facts["project_name"] == "Nimbus"
    assert facts["assumed_team_size"] == 5
    assert set(facts["mentioned_technologies"]) == {"Python", "React", "Stripe"}
    assert "reservar salas" in facts["agreed_scope"] and "calendario" in facts["agreed_scope"]
    assert '"project_name":"Nimbus"' in api.calls[1][0]["content"]
    assert '"assumed_team_size":3' in api.calls[1][0]["content"]
    assert len(api.calls[1]) == 4
    assert second.json()["prompt_version"] == "v2"
    info = await api.client.get(f"/sessions/{session_id}")
    assert info.json()["project_metadata"] == facts


async def test_pdf_content_changes_the_validated_estimate(api):
    plain_id, attached_id = await create(api), await create(api)
    plain = await estimate(api, plain_id, "Estima el proyecto Nimbus.")
    attached = await estimate(api, attached_id, "Estima el proyecto Nimbus.", [
        ("spec.pdf", pdf_bytes(), "application/pdf"),
    ])
    assert attached.status_code == 200, attached.text
    assert plain.json()["result"]["total_cost_eur"] == 1000
    assert attached.json()["result"]["total_cost_eur"] == 2500
    assert "--- attachment: spec.pdf ---" in api.calls[-1][-1]["content"]
    assert "INTEGRACION_SAP" in api.calls[-1][-1]["content"]


async def test_eight_turns_bound_effective_history_and_keep_project_facts(api):
    session_id = await create(api)
    for turn in range(8):
        transcript = "Proyecto: Nimbus. Equipo: 3." if turn == 0 else f"Refinamiento {turn}."
        response = await estimate(api, session_id, transcript)
        assert response.status_code == 200, response.text
    assert len(api.calls) == 8
    for messages in api.calls:
        assert len(messages) <= 2 * 3 + 2
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
    assert "Proyecto: Nimbus" not in str(api.calls[-1][1:])
    assert '"project_name":"Nimbus"' in api.calls[-1][0]["content"]
    assert api.store.get(session_id).history.turn_count == 3
    assert response.json()["history_turns"] == 3


async def test_word_extracts_tables_and_current_turn_overrides_attachment(api):
    session_id = await create(api)
    response = await estimate(api, session_id, "Proyecto: Nuevo nombre.", [
        ("spec.docx", docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ])
    assert response.status_code == 200, response.text
    facts = response.json()["project_metadata"]
    assert facts["project_name"] == "Nuevo nombre"
    assert set(facts["mentioned_technologies"]) == {"Python", "PostgreSQL"}


@pytest.mark.parametrize("filename,content,status", [
    ("spec.txt", b"text", 415), ("spec.doc", b"old word", 415),
    ("broken.pdf", b"broken", 422), ("broken.docx", b"broken", 422),
    ("scan.pdf", pdf_bytes(""), 422),
])
async def test_bad_attachments_fail_before_llm_without_state_change(api, filename, content, status):
    session_id = await create(api)
    response = await estimate(api, session_id, "Proyecto: Privado.", [(filename, content, "application/octet-stream")])
    assert response.status_code == status
    assert not api.calls
    assert api.store.get(session_id).history.turn_count == 0
    assert api.store.get(session_id).metadata.is_empty()


async def test_limits_fail_before_llm(api, monkeypatch):
    from app.routers.sessions import settings
    session_id = await create(api)
    with monkeypatch.context() as patch:
        patch.setattr(settings, "MAX_ATTACHMENT_BYTES", 10)
        response = await estimate(api, session_id, "Proyecto.", [("spec.pdf", pdf_bytes(), "application/pdf")])
        assert response.status_code == 413
    with monkeypatch.context() as patch:
        patch.setattr(settings, "MAX_ATTACHMENT_CHARS", 3)
        response = await estimate(api, session_id, "Proyecto.", [("spec.pdf", pdf_bytes(), "application/pdf")])
        assert response.status_code == 413
    with monkeypatch.context() as patch:
        patch.setattr(settings, "MAX_CONTEXT_CHARS", 3)
        response = await estimate(api, session_id, "Proyecto.")
        assert response.status_code == 413
    assert not api.calls


async def test_unknown_session_and_invalid_form_do_not_call_llm(api):
    response = await estimate(api, "missing", "Proyecto.")
    assert response.status_code == 404
    session_id = await create(api)
    for transcript, options in [("  ", {}), ("Proyecto.", {"project_type": "invalid"})]:
        response = await estimate(api, session_id, transcript, **options)
        assert response.status_code == 422
    assert not api.calls


async def test_provider_failure_preserves_previous_state_and_sanitizes_error(api, monkeypatch):
    session_id = await create(api)
    await estimate(api, session_id, "Proyecto: Nimbus.")
    session = api.store.get(session_id)
    before = session.history.to_messages_list(system_prompt="system")
    metadata = session.metadata.model_dump()
    async def fail(messages):
        raise LLMServiceError("invalid_response")
    monkeypatch.setattr(conversation, "generate_structured_estimation", fail)
    response = await estimate(api, session_id, "Proyecto: No guardar.")
    assert response.status_code == 502
    assert session.metadata.model_dump() == metadata
    assert session.history.to_messages_list(system_prompt="system") == before


async def test_new_sessions_are_isolated_and_parallel_turns_are_serialized(api):
    first, second = await create(api), await create(api)
    await estimate(api, first, "Proyecto: Nimbus.")
    other = await api.client.get(f"/sessions/{second}")
    assert other.json()["project_metadata"]["project_name"] is None
    responses = await asyncio.gather(
        estimate(api, first, "Añade calendario."),
        estimate(api, first, "Añade facturación."),
    )
    assert all(response.status_code == 200 for response in responses)
    assert [len(messages) for messages in api.calls] == [2, 4, 6]
    assert api.store.get(first).history.turn_count == 3
