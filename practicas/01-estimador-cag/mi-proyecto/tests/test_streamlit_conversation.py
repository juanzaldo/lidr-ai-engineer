from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from test_sessions_integration import result_payload


@pytest.fixture
def ui(monkeypatch):
    state = SimpleNamespace(calls=[], uploads=[], session_id=None, turns=0, failure=None)
    def post(url, **kwargs):
        state.calls.append((url, kwargs))
        if state.failure:
            return httpx.Response(state.failure, request=httpx.Request("POST", url), json={"detail": "private-provider-secret"})
        if url.endswith("/sessions"):
            state.session_id = str(uuid4())
            state.turns = 0
            body, status = {"session_id": state.session_id}, 201
        else:
            state.turns += 1
            body, status = {
                "session_id": state.session_id, "result": result_payload(), "prompt_version": "v2",
                "project_metadata": {"project_name": "Nimbus", "assumed_team_size": state.turns + 1,
                                     "mentioned_technologies": ["Python"], "agreed_scope": "Reservas"},
                "history_turns": state.turns, "max_turns": 6,
            }, 200
        return httpx.Response(status, request=httpx.Request("POST", url), json=body)
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr("streamlit.file_uploader", lambda *args, **kwargs: state.uploads)
    state.app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=30,
    ).run()
    assert not state.app.exception
    return state


def submit(ui, text="Proyecto: Nimbus."):
    ui.app.text_area[0].set_value(text)
    ui.app.button(key="estimate").click().run()
    assert not ui.app.exception


def test_ui_three_turns_keep_session_and_show_metadata(ui):
    session_id = ui.app.session_state.session_id
    for index, text in enumerate(("Proyecto: Nimbus.", "Añade calendario.", "Equipo: 4.")):
        submit(ui, text)
        assert ui.app.session_state.session_id == session_id
        assert len(ui.app.session_state.estimations) == index + 1
        assert ui.app.session_state.project_metadata["assumed_team_size"] == index + 2
        assert ui.app.sidebar.json
    ui.app.run()
    assert len(ui.calls) == 4  # Una creación y tres estimaciones, sin reenvío al rerun.
    assert all(url.endswith(f"/{session_id}/estimate") for url, _ in ui.calls[1:])
    fields = {name: value[1] for name, value in ui.calls[-1][1]["files"]}
    assert fields["transcript"] == "Equipo: 4."
    assert fields["project_type"] == "web_saas"


def test_ui_new_conversation_resets_metadata_history_and_input(ui):
    submit(ui)
    old = ui.app.session_state.session_id
    ui.app.button(key="new_conversation").click().run()
    assert not ui.app.exception
    assert ui.app.session_state.session_id != old
    assert ui.app.session_state.estimations == []
    assert ui.app.session_state.project_metadata["project_name"] is None
    assert ui.app.text_area[0].value == ""


def test_ui_forwards_multiple_attachments_and_selected_options(ui):
    ui.uploads = [
        SimpleNamespace(name="spec.pdf", size=3, type="application/pdf", getvalue=lambda: b"pdf"),
        SimpleNamespace(name="spec.docx", size=4, type="application/octet-stream", getvalue=lambda: b"docx"),
    ]
    ui.app.selectbox[2].select("narrative")
    submit(ui)
    parts = ui.calls[-1][1]["files"]
    assert [part[1][0] for part in parts if part[0] == "attachments"] == ["spec.pdf", "spec.docx"]
    assert ("output_format", (None, "narrative")) in parts
    assert not ui.app.table


def test_ui_invalid_input_never_requests_estimation(ui):
    submit(ui, "   ")
    assert len(ui.calls) == 1
    assert ui.app.error


@pytest.mark.parametrize("status", [404, 422, 502])
def test_ui_failure_keeps_previous_conversation_and_hides_private_errors(ui, status):
    submit(ui)
    ui.failure = status
    submit(ui, "Añade facturación.")
    assert ui.app.error
    assert "private-provider-secret" not in ui.app.error[0].value
    assert len(ui.app.session_state.estimations) == 1
    if status == 404:
        assert "Nueva conversación" in ui.app.error[0].value
