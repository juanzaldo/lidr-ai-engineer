"""Cliente conversacional; la memoria del proyecto pertenece a FastAPI."""
import os

import httpx
from pydantic import ValidationError
import streamlit as st

from app.schemas.estimation import DetailLevel, OutputFormat, ProjectType
from app.schemas.session import CreateSessionResponse, SessionEstimationResponse, SessionRequest
from app.sessions import ProjectMetadata


API_URL = os.getenv("ESTIMATOR_API_URL", "http://127.0.0.1:8000").rstrip("/")
LABELS = {
    "web_saas": "Web / SaaS", "mobile_app": "Aplicación móvil",
    "internal_tool": "Herramienta interna", "data_pipeline": "Pipeline de datos",
    "summary": "Resumen", "medium": "Medio", "detailed": "Detallado",
    "phases_table": "Tabla por fases", "line_items": "Lista de tareas", "narrative": "Narrativo",
}


def show_error(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        message = {
            404: "La conversación ya no existe. Pulsa Nueva conversación para continuar.",
            413: "El texto o los adjuntos superan el límite. Divide el contenido.",
            415: "Solo se admiten documentos PDF y Word .docx.",
            422: "Revisa los campos y los adjuntos: deben ser legibles y contener texto.",
            500: "El servicio necesita revisar su configuración o sus registros.",
            502: "El proveedor no pudo devolver una estimación válida. Puedes reintentar.",
            503: "El proveedor está temporalmente ocupado. Inténtalo más tarde.",
            504: "El proveedor tardó demasiado. Inténtalo de nuevo.",
        }.get(exc.response.status_code, "El servicio no pudo completar la petición.")
    elif isinstance(exc, httpx.RequestError):
        message = "No se pudo contactar con la API. Comprueba que FastAPI esté iniciado."
    else:
        message = "La API devolvió una respuesta con formato inesperado."
    st.error(message)


def new_conversation() -> bool:
    try:
        response = httpx.post(f"{API_URL}/sessions", timeout=15.0)
        response.raise_for_status()
        created = CreateSessionResponse.model_validate(response.json())
    except (httpx.HTTPError, ValidationError, ValueError) as exc:
        show_error(exc)
        return False
    st.session_state.session_id = str(created.session_id)
    st.session_state.estimations = []
    st.session_state.project_metadata = ProjectMetadata().model_dump()
    st.session_state.history_turns = 0
    st.session_state.max_turns = 6
    st.session_state.form_generation = st.session_state.get("form_generation", 0) + 1
    return True


st.set_page_config(page_title="Estimador CAG", page_icon="📝", layout="wide")
st.title("Estimador de software")
st.caption("Refina el mismo proyecto entre turnos y añade documentación PDF o Word.")

restart = st.button("Nueva conversación", key="new_conversation")
if restart:
    new_conversation()
elif "session_id" not in st.session_state:
    new_conversation()
if "session_id" not in st.session_state:
    st.stop()

generation = st.session_state.form_generation
with st.form("conversation_form"):
    transcript = st.text_area(
        "Transcripción o cambio de alcance", key=f"transcript_{generation}",
        height=150, max_chars=80_000,
        help="Para fijar hechos usa, por ejemplo: Proyecto: Nimbus. Equipo: 3. Alcance: reservar salas.",
    )
    attachments = st.file_uploader(
        "Adjuntos (opcional)", type=["pdf", "docx"], accept_multiple_files=True,
        key=f"attachments_{generation}",
        help="Hasta 5 archivos, 5 MB por archivo y 10 MB en total. PDF con texto o Word .docx; sin OCR.",
    )
    project_type = st.selectbox("Tipo de proyecto", list(ProjectType), index=1, format_func=LABELS.get)
    detail_level = st.selectbox("Nivel de detalle", list(DetailLevel), index=1, format_func=LABELS.get)
    output_format = st.selectbox("Formato de salida", list(OutputFormat), format_func=LABELS.get)
    submitted = st.form_submit_button("Generar estimación", type="primary", key="estimate")

if submitted:
    try:
        request = SessionRequest(
            transcript=transcript, project_type=project_type,
            detail_level=detail_level, output_format=output_format,
        )
    except ValidationError:
        st.error("Escribe una transcripción de entre 1 y 80000 caracteres útiles.")
    else:
        if len(attachments) > 5 or any(file.size > 5_000_000 for file in attachments) or sum(file.size for file in attachments) > 10_000_000:
            st.error("Los adjuntos superan el límite: 5 archivos, 5 MB cada uno y 10 MB en total.")
        else:
            # Los campos con filename=None fuerzan multipart incluso sin adjuntos.
            files = [(name, (None, value)) for name, value in request.model_dump(mode="json").items()]
            files.extend(("attachments", (file.name, file.getvalue(), file.type)) for file in attachments)
            try:
                with st.spinner("Actualizando la estimación…"):
                    response = httpx.post(
                        f"{API_URL}/sessions/{st.session_state.session_id}/estimate",
                        files=files, timeout=120.0,
                    )
                    response.raise_for_status()
                    result = SessionEstimationResponse.model_validate(response.json())
                    if str(result.session_id) != st.session_state.session_id:
                        raise ValueError("La respuesta pertenece a otra sesión")
                st.session_state.estimations.append({
                    "transcript": transcript, "attachments": [file.name for file in attachments],
                    "output_format": output_format.value, "response": result.model_dump(mode="json"),
                })
                st.session_state.project_metadata = result.project_metadata.model_dump()
                st.session_state.history_turns = result.history_turns
                st.session_state.max_turns = result.max_turns
                st.session_state.form_generation += 1
                st.rerun()
            except (httpx.HTTPError, ValidationError, ValueError) as exc:
                show_error(exc)

with st.sidebar:
    st.subheader("Hechos del proyecto")
    st.json(st.session_state.project_metadata)
    st.caption(f"Turnos recientes: {st.session_state.history_turns} / {st.session_state.max_turns}")
    st.caption(f"Sesión: {st.session_state.session_id}")
    st.caption("Los hechos sobreviven al recorte del historial. Reiniciar la API borra la conversación.")

for turn in st.session_state.estimations:
    with st.chat_message("user"):
        st.write(turn["transcript"])
        if turn["attachments"]:
            st.caption("Adjuntos: " + ", ".join(turn["attachments"]))
    with st.chat_message("assistant"):
        response = SessionEstimationResponse.model_validate(turn["response"])
        result = response.result
        st.write(result.summary)
        if turn["output_format"] == "phases_table":
            st.table([{
                "Fase": phase.name, "Semanas": phase.duration_weeks,
                "Coste EUR": phase.cost_eur, "Entregable / supuestos": phase.summary,
            } for phase in result.phases])
        else:
            for phase in result.phases:
                prefix = "• " if turn["output_format"] == "line_items" else ""
                st.write(f"{prefix}{phase.name}: {phase.summary} ({phase.duration_weeks} semanas, {phase.cost_eur:,.0f} EUR).")
        st.caption(
            f"Total: {result.total_cost_eur:,.0f} EUR · {result.total_duration_weeks} semanas · "
            f"Confianza: {result.confidence_pct}% · Prompt {response.prompt_version}"
        )
