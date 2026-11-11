# Estimador CAG · Sesión 5

FastAPI y Streamlit para refinar una estimación de software durante una
conversación. Cada sesión conserva los hechos del proyecto y los últimos seis
turnos. Admite documentación PDF y Word y devuelve estimaciones estructuradas
validadas con Pydantic. Rama de entrega: `pre-session-05`.

## Arranque

Desde esta carpeta, con Python 3.11 o superior:

```powershell
uv sync --locked --dev
```

Solo en la primera instalación, copia `.env.example` a `.env` y configura las
claves localmente. Conserva tu `.env` si ya existe. Elige `LLM_PROVIDER=openai`
y `LLM_MODEL=gpt-4o-mini`, o `LLM_PROVIDER=anthropic` y
`LLM_MODEL=claude-haiku-4-5`, junto con la clave correspondiente. Reinicia la
API si cambias configuración. No subas claves a Git.

En una terminal:

```powershell
uv run --locked uvicorn app.main:app --reload
```

En otra terminal, desde la misma carpeta:

```powershell
uv run --locked streamlit run streamlit_app.py
```

Abre [Streamlit](http://localhost:8501) y [Swagger](http://localhost:8000/docs).
El cliente usa `http://127.0.0.1:8000`; puedes cambiarlo mediante
`ESTIMATOR_API_URL`. Utiliza **un solo worker**: las sesiones viven en un
diccionario del proceso y se pierden al reiniciar, también con `--reload`.
Crear una sesión o consultar sus hechos no llama al modelo. Generar una
estimación sí envía la transcripción y el texto de los adjuntos al proveedor
y consume tokens. La prueba real sigue pendiente de autorización.

## Probar una conversación

1. El cliente crea la sesión al cargar y guarda su UUID en `session_state`.
2. Primer turno: `Proyecto: Nimbus. Equipo: 3. Alcance: reservar salas.`
   Añade en otra línea `Tecnologías: Python y React.`
3. Segundo turno: `Añade calendario y Stripe.` Puedes adjuntar una especificación.
4. Tercer turno: `Equipo: 5. Alcance: reservas y calendario, sin facturación.`
5. Comprueba el panel «Hechos del proyecto» y las estimaciones por turno.
   «Nueva conversación» crea otro UUID y limpia el formulario y sus resultados.

Los formatos tabla, lista y narrativo se presentan en el cliente a partir
del mismo resultado tipado. Los costes del proyecto están en **EUR**, conforme
al schema de la referencia; no son el coste en USD de la llamada al proveedor.
El template declara supuestos ficticios si faltan tarifa o equipo.

## Contrato HTTP

| Endpoint | Entrada / salida |
| --- | --- |
| `POST /sessions` | Sin cuerpo; 201 con `session_id` UUID |
| `GET /sessions/{session_id}` | Metadatos, turnos almacenados y tamaño de ventana |
| `POST /sessions/{session_id}/estimate` | multipart/form-data; resultado y estado actualizado |

La estimación recibe `transcript` (1 a 80000 caracteres, no solo espacios) y
varios archivos opcionales en el campo repetido `attachments`. Acepta también
`project_type`, `detail_level` y `output_format`. Sus valores por defecto son
`web_saas`, `medium` y `phases_table`, por lo que se puede enviar únicamente
la transcripción. Los enums conservan los valores de sesión 4:

- Tipo: `mobile_app`, `web_saas`, `internal_tool`, `data_pipeline`.
- Detalle: `summary`, `medium`, `detailed`.
- Formato: `phases_table`, `line_items`, `narrative`.

La respuesta contiene `result` (resumen, confianza, fases, semanas y coste
total), `prompt_version`, `session_id`, `project_metadata`, `history_turns` y
`max_turns`. Pydantic verifica tipos, límites, suma exacta de costes y el
prefijo `Out of scope:` si la confianza es menor de 30. Las fases pueden
solaparse, por lo que su duración no tiene que sumar la duración total.

Los errores devuelven 404 para sesión desconocida, 413 para límites, 415 para
formatos no admitidos, 422 para campos o documentos ilegibles y 502/503/504
para errores del proveedor. Una estimación fallida no añade medio turno ni
cambia los hechos. Un lock por sesión ordena las peticiones simultáneas.

## Memoria y prompts

`ConversationHistory` guarda pares user/assistant. Con N=6 envía hasta seis
pares anteriores, el system regenerado y el user actual: máximo 14 mensajes.
La ventana limita turnos, no tokens. `ProjectMetadata` vive aparte y conserva
nombre, equipo asumido, tecnologías y alcance aunque se eliminen turnos antiguos.
No es un resumen de todo lo dicho.

Los templates `app/prompts/estimation/v2/` incluyen el bloque
`<project_metadata>`, vacío al inicio, instrucciones de salida estructurada
y dos ejemplos ficticios. El loader usa `StrictUndefined`. OpenAI recibe
JSON Schema y Anthropic una herramienta forzada que solo transporta el
objeto del resultado; no se ejecuta ninguna función externa. Pydantic aplica
las mismas reglas localmente a ambos proveedores. No hay reintentos LLM
automáticos ni caché de respuestas en este flujo.

### Extracción de hechos por heurística

Elegimos regex y reglas sencillas para evitar una segunda llamada por turno.
Después de una respuesta válida se buscan `Proyecto:`, `Equipo:`, `Alcance:`
y expresiones como `se llama` o `Añade`. El alcance explícito reemplaza el
anterior; las adiciones se acumulan. Las tecnologías reconocidas se acumulan,
y expresiones simples como `Sin React` las eliminan. El texto explícito del
turno prevalece sobre el adjunto. Del modelo solo se acepta `Equipo asumido: N`
si aún no hay equipo conocido; sus propuestas no se convierten en alcance acordado.

Limitación: no comprende todas las paráfrasis, negaciones o nombres de
tecnologías. Para corregir hechos usa las etiquetas del ejemplo. El campo de
alcance está acotado a 2000 caracteres. Un extractor LLM sería más flexible,
pero añadiría coste y otra llamada; queda fuera de esta entrega.

### Adjuntos: camino B

Extraemos localmente con `pypdf` y `python-docx`, incluyendo párrafos y tablas
Word. El texto se añade al turno con `--- attachment: nombre.pdf ---`. Esto
mantiene independencia del proveedor y prepara la separación en fragmentos
para RAG. El archivo no se persiste como documento del proyecto; el texto sí
permanece en la ventana mientras su turno esté retenido. El servidor multipart
puede usar almacenamiento temporal durante la recepción.

Se admiten `.pdf` con texto y `.docx`. No se realiza OCR, lectura visual de
diagramas ni conversión de `.doc`. Los archivos corruptos, cifrados o sin texto
se rechazan explícitamente. Se rechaza el exceso de texto en lugar de truncar
requisitos silenciosamente. Los parsers se ejecutan fuera del bucle asíncrono.

| Variable de `.env` | Valor por defecto |
| --- | ---: |
| `MAX_CONVERSATION_TURNS` | 6 |
| `MAX_ATTACHMENTS` | 5 |
| `MAX_ATTACHMENT_BYTES` | 5000000 por archivo |
| `MAX_TOTAL_ATTACHMENT_BYTES` | 10000000 por petición |
| `MAX_ATTACHMENT_CHARS` | 60000 por archivo |
| `MAX_CONTEXT_CHARS` | 80000 para transcripción enriquecida |

El cliente aplica los límites de archivo de la tabla; el backend permite
ajustarlos, pero el cliente no descubre esos cambios automáticamente. Además
se limitan los PDF a 200 páginas y el DOCX descomprimido a 20 MB. Es una práctica
local sin autenticación ni persistencia; estos límites no sustituyen el control
de tamaño de petición y aislamiento de parsers de un despliegue público.

## Pruebas

```powershell
uv run --locked python -m pytest -q
uv run --locked python -m pytest tests/test_sessions_integration.py -v
```

**71 pruebas y 139 subcasos aprobados** localmente. Pytest ejecuta también
las pruebas `unittest` anteriores. Las pruebas de integración usan
`httpx.AsyncClient` y `ASGITransport` con SDK/proveedor simulado: dos turnos
actualizan hechos, un PDF cambia una cifra del resultado simulado y ocho
turnos respetan la ventana enviada. AppTest comprueba tres turnos visibles,
reinicio, errores y carga múltiple. La red y los SDK reales están bloqueados
en la suite; no se necesita `.env` ni Uvicorn para ejecutarla.

GitHub Actions ejecuta la misma suite con dependencias bloqueadas. Las pruebas
no acreditan la calidad semántica de un modelo real ni disponibilidad de cuenta.

## Compatibilidad y entrega

`POST /estimate` conserva la entrada tipada de sesión 4 y su respuesta
`text`/`prompt_version`, con templates `v1`. `/api/v1/estimate` conserva la
transcripción y las métricas de sesión 3. El formulario transaccional anterior
está disponible con `uv run --locked streamlit run streamlit_legacy.py`.

Consulta la [guía final de sesión 5](../guia-session-5.md) y la
[rama de entrega](https://github.com/juanzaldo/lidr-ai-engineer/tree/pre-session-05).
