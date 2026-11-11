"""Formulario transaccional de sesión 4 conservado para compatibilidad."""
import os

import httpx
from pydantic import ValidationError
import streamlit as st

from app.schemas.estimation import (
    DetailLevel, EstimationRequest, EstimationResponse, OutputFormat, ProjectType,
)


API_URL = os.getenv("ESTIMATOR_API_URL", "http://127.0.0.1:8000").rstrip("/")
PROJECT_LABELS = {
    ProjectType.MOBILE_APP: "Aplicación móvil",
    ProjectType.WEB_SAAS: "Web / SaaS",
    ProjectType.INTERNAL_TOOL: "Herramienta interna",
    ProjectType.DATA_PIPELINE: "Pipeline de datos",
}
DETAIL_LABELS = {
    DetailLevel.SUMMARY: "Resumen",
    DetailLevel.MEDIUM: "Medio",
    DetailLevel.DETAILED: "Detallado",
}
FORMAT_LABELS = {
    OutputFormat.PHASES_TABLE: "Tabla por fases",
    OutputFormat.LINE_ITEMS: "Lista de tareas",
    OutputFormat.NARRATIVE: "Narrativo",
}

st.set_page_config(page_title="Estimador CAG", page_icon="📝")
st.title("Estimador de software")
st.caption("Describe el alcance y elige cómo quieres recibir la estimación.")

if "estimations" not in st.session_state:
    st.session_state.estimations = []

with st.form("estimation_form"):
    description = st.text_area(
        "Descripción del proyecto", height=180, max_chars=2000,
        help="Entre 20 y 2000 caracteres. Incluye alcance, usuarios e integraciones.",
    )
    project_type = st.selectbox(
        "Tipo de proyecto", options=list(ProjectType), index=1,
        format_func=PROJECT_LABELS.get,
    )
    detail_level = st.selectbox(
        "Nivel de detalle", options=list(DetailLevel), index=1,
        format_func=DETAIL_LABELS.get,
    )
    output_format = st.selectbox(
        "Formato de salida", options=list(OutputFormat),
        format_func=FORMAT_LABELS.get,
    )
    submitted = st.form_submit_button("Generar estimación", type="primary")

if submitted:
    try:
        request = EstimationRequest(
            description=description, project_type=project_type,
            detail_level=detail_level, output_format=output_format,
        )
    except ValidationError:
        st.error("La descripción debe contener entre 20 y 2000 caracteres útiles.")
    else:
        try:
            with st.spinner("Generando estimación…"):
                response = httpx.post(
                    f"{API_URL}/estimate",
                    json=request.model_dump(mode="json"),
                    timeout=90.0,
                )
                response.raise_for_status()
                result = EstimationResponse.model_validate(response.json())
            st.session_state.estimations.append({
                "description": description,
                "text": result.text,
                "prompt_version": result.prompt_version,
            })
        except httpx.HTTPStatusError as exc:
            message = {
                422: "Revisa los campos del formulario.",
                500: "El servicio necesita revisar su configuración o sus registros.",
                502: "El proveedor rechazó la solicitud o devolvió una respuesta incompleta.",
                503: "El proveedor está temporalmente ocupado. Inténtalo más tarde.",
                504: "El proveedor tardó demasiado. Inténtalo de nuevo.",
            }.get(exc.response.status_code, "El servicio no pudo completar la estimación.")
            st.error(message)
        except httpx.RequestError:
            st.error("No se pudo contactar con la API. Comprueba que FastAPI esté iniciado.")
        except (ValidationError, ValueError):
            st.error("La API devolvió una respuesta con formato inesperado.")

for estimation in reversed(st.session_state.estimations):
    st.divider()
    st.caption(estimation["description"])
    st.markdown(estimation["text"])
    st.caption(f'Versión del prompt · {estimation["prompt_version"]}')
