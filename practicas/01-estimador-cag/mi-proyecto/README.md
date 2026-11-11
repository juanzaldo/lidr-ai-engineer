# Estimador CAG · Sesión 4

Formulario Streamlit que envía una descripción, tipo de proyecto, nivel de
detalle y formato a FastAPI. Jinja2 construye los mensajes desde templates
versionados y el servicio utiliza el proveedor OpenAI o Anthropic configurado.

## Ejecutar

Desde esta carpeta, instala las dependencias con `uv sync --locked --dev`.
En la primera instalación, copia `.env.example` a `.env` y configura las claves
localmente. El proveedor y modelo se eligen en `.env` con `LLM_PROVIDER` y
`LLM_MODEL`. Los valores predeterminados son `openai` y `gpt-4o-mini`.
Para Anthropic, configura ambos valores, por ejemplo `anthropic` y
`claude-haiku-4-5`. Reinicia la API tras cambiar la configuración.

En una terminal, inicia la API.

```powershell
uv run --locked uvicorn app.main:app --reload
```

En otra terminal, desde la misma carpeta, inicia el formulario.

```powershell
uv run --locked streamlit run streamlit_app.py
```

Abre el formulario en http://localhost:8501 y Swagger en http://localhost:8000/docs.
El cliente usa `http://127.0.0.1:8000` como dirección de la API. Puedes cambiarla
con la variable de entorno `ESTIMATOR_API_URL` antes de iniciar Streamlit.

## Contrato

`POST /estimate` recibe este JSON de ejemplo.

```json
{
  "description": "Una herramienta interna para registrar préstamos y devoluciones de equipo.",
  "project_type": "internal_tool",
  "detail_level": "detailed",
  "output_format": "phases_table"
}
```

La descripción admite de 20 a 2000 caracteres. Los tipos disponibles son
`mobile_app`, `web_saas`, `internal_tool` y `data_pipeline`. El detalle admite
`summary`, `medium` y `detailed`. Los formatos son `phases_table`, `line_items`
y `narrative`. La respuesta contiene `text` con Markdown y `prompt_version`.

Los templates viven en `app/prompts/estimation/v1/`. El loader usa
`StrictUndefined` para detectar variables ausentes y devuelve los mensajes
system y user por separado. `examples.j2` contiene dos proyectos ficticios.
La versión se establece en `PROMPT_VERSION` dentro del router.

Por compatibilidad, `/api/v1/estimate` sigue aceptando `transcription` y devolviendo
el contrato con métricas de la sesión 3. Las funciones Python de streaming
siguen disponibles. El formulario de la sesión 4 utiliza la respuesta completa
de `/estimate` y guarda los resultados durante la sesión del navegador.

## Pruebas

```powershell
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m unittest discover -s tests/prompts -v
```

Las pruebas usan proveedores simulados y verifican templates, validación,
mensajes separados, errores controlados, compatibilidad y envío del formulario.
GitHub Actions ejecuta la suite en cada push.

Consulta la [guía de la sesión 4](../guia-session-4.md) para conocer las decisiones,
el alcance de la validación y el enlace de entrega.
