# Guía de la sesión 5 · Estimador CAG

## Resultado y estado

11 de noviembre de 2026. Implementación y validación local terminadas en
`pre-session-05`: sesiones conversacionales, memoria acotada, metadatos,
adjuntos PDF/DOCX, resultados estructurados y cliente Streamlit.
Pasaron **71 pruebas y 139 subcasos en 10.66 s**, con proveedores simulados.
La rama está publicada y GitHub Actions aprobó el commit de implementación.
La entrega queda cerrada, con la prueba real del proveedor pendiente de autorización.

## Base y referencia verificadas

Se leyeron `prompt-session-5.md`, `guia-session-4.md`, el README del proyecto
y el enunciado adjunto `Texto pegado.txt`. La base personal estaba limpia:
`pre-session-04`, commit `0a2515f70d7a761fa16bf3d03bd84e539ee3c728`, sin
diferencias con `origin/pre-session-04` después de `git fetch origin`.
Se creó `pre-session-05` a partir de esa base.

En el clon del maestro se consultó `origin/session_5` (`4a4de0d`) mediante
`git show`, sin alterar su checkout `session_2`. La rama `solutions/session-05`
citada en el enunciado no aparecía entre las referencias después del fetch.

| Aspecto | Maestro | Decisión personal |
| --- | --- | --- |
| Cliente | Rails conversacional | Conservar Streamlit y añadir el flujo conversacional |
| Proveedores | LiteLLM e Instructor | Adaptar los SDK OpenAI/Anthropic existentes |
| Metadatos | Segunda llamada al LLM | Heurística explícita, permitida en el enunciado |
| Adjuntos | Extracción local PDF/DOCX | Mismo camino B; incluir tablas Word y rechazar documentos vacíos |
| Resultado | EstimationResult tipado | Incorporarlo al nuevo flujo, conservando contratos anteriores |
| Caché | Exacta y semántica; se omiten en conversaciones | Sin caché propia; no se añadió para este ejercicio |
| Observabilidad | structlog | Conservar logging JSON y errores públicos controlados |
| Integración | TestClient y wrapper simulado | pytest + httpx.AsyncClient/ASGITransport, como pide el enunciado |

La base personal solo validaba el contenedor de Markdown. El enunciado
presupone salida estructurada, por lo que se incluyó esa brecha en el alcance.
No se importó toda la arquitectura de cachés y guardrails del maestro.

## Cómo funciona un turno

1. Streamlit crea una sesión con `POST /sessions` y guarda el UUID en
   `session_state`. Se puede consultar con `GET /sessions/{session_id}`.
2. El formulario envía `transcript`, las opciones tipadas y los archivos
   opcionales como multipart a `POST /sessions/{session_id}/estimate`.
3. FastAPI valida los campos y límites, extrae texto localmente y añade
   separadores con el nombre del adjunto. Los parsers se ejecutan fuera del
   bucle asíncrono. Los documentos ilegibles no se ignoran en silencio.
4. Un lock por sesión ordena las estimaciones concurrentes. El loader Jinja2
   renderiza `estimation/v2/` con los hechos actuales y ejemplos ficticios.
5. Se envía system + los últimos N pares + el nuevo user. OpenAI recibe los
   roles juntos; Anthropic recibe system en su parámetro separado.
6. El resultado se valida con Pydantic. Solo entonces se actualizan los hechos
   y se confirma el par user/assistant. Un fallo no deja un turno parcial.
7. La API devuelve resultado, versión del prompt y metadatos. Streamlit muestra
   el formato elegido, conserva los resultados del navegador y actualiza el panel.

## Historial frente a memoria

`ConversationHistory` es la lista limitada que viaja al proveedor. Se conservan
seis pares completos por defecto; el séptimo desplaza al primero. El system
se regenera desde los metadatos y nunca se descarta. El máximo enviado es
`2 * MAX_CONVERSATION_TURNS + 2`: 14 mensajes con la configuración inicial.
Incluye seis turnos anteriores más el nuevo user y system.

`ProjectMetadata` conserva hechos separados: `project_name`,
`assumed_team_size`, `mentioned_technologies` y `agreed_scope`. Esos hechos
no desaparecen al recortar el historial. El bloque `<project_metadata>` del
primer turno está vacío; las estimaciones posteriores reciben los hechos
actualizados. Los metadatos no son una copia ni un resumen de todo el historial.

La ventana es un punto de partida sencillo y predecible. Limita mensajes,
no tokens, y pierde detalles antiguos que no se hayan capturado como hechos.
Eso motiva el resumen acumulativo y las anclas del directo. El store es un
diccionario volátil: reiniciar FastAPI elimina las sesiones y se utiliza un
solo worker. No hay BBDD ni Redis.

## Extracción de hechos y sus límites

La heurística evita una segunda llamada por turno. Reconoce etiquetas como
`Proyecto: Nimbus`, `Equipo: 3` y `Alcance: reservar salas`, además de
`se llama`, `llamado` y adiciones con `Añade`, `Agrega` o `Incluye`.
Un alcance explícito reemplaza al previo; las adiciones se acumulan. Se unen
tecnologías de un vocabulario conocido y se admiten negaciones simples como
`Sin React` o `No usar Python`.

Se priorizan los hechos explícitos del turno sobre los del adjunto. El nombre
y alcance no se extraen de sugerencias del modelo. Solo se acepta de su
resumen `Equipo asumido: N` cuando no hay equipo conocido. Se actualiza una
copia de los metadatos para evitar modificar el estado si falla la validación.

No es extracción semántica general: puede no entender paráfrasis, tecnologías
fuera del vocabulario o negaciones complejas. El alcance tiene un límite de
2000 caracteres. Las etiquetas del ejemplo permiten corregir los hechos de
forma reproducible. El panel muestra el estado para que el alumno lo inspeccione.

## Adjuntos: camino B

Se eligió `pypdf` para PDF y `python-docx` para Word, incluyendo párrafos y
tablas. El texto se concatena con `--- attachment: archivo.pdf ---` y se
envía al proveedor como parte del turno. El archivo no se guarda como
documento persistente; el texto vive en la ventana mientras se retiene su turno.
El receptor multipart puede usar archivos temporales para recibir la subida.

Esto conserva independencia de proveedor y prepara el terreno para chunking
en RAG. El camino A usaría capacidades multimodales/Files API y sería útil
si hubiera que interpretar páginas como imágenes; aquí no se usa.

Límites predeterminados: cinco archivos, 5 MB cada uno, 10 MB en total,
60000 caracteres por adjunto y 80000 para el turno enriquecido. Se rechaza
el exceso, sin truncar requisitos silenciosamente. El PDF se limita a 200
páginas y el DOCX descomprimido a 20 MB. Se rechazan archivos cifrados,
corruptos, sin texto y extensiones distintas de `.pdf`/`.docx`.
No hay OCR, interpretación de diagramas ni soporte para Word `.doc`.

## Salida y compatibilidad

`EstimationResult` contiene fases, semanas, costes EUR, resumen y confianza.
Valida tipos estrictos, límites y suma exacta de costes. Confianza menor de
30 exige el prefijo `Out of scope:`. Se permiten fases paralelas, por lo que
su duración no se suma obligatoriamente. El coste del proyecto en EUR es
distinto del coste estimado de la llamada al proveedor en USD.

OpenAI recibe JSON Schema estricto; Anthropic devuelve una herramienta
forzada que únicamente transporta el objeto del resultado. No se ejecutan
funciones externas. Ambos resultados pasan por Pydantic. No hay reintentos
automáticos ni corrección silenciosa de cifras; los fallos retornan errores
controlados. Los logs de la aplicación omiten prompts y contenidos privados.

`POST /estimate` mantiene `text`/`prompt_version` y templates `v1`.
`/api/v1/estimate` conserva el contrato de sesión 3. El formulario anterior
se conserva en `streamlit_legacy.py`, con sus pruebas. El nuevo formulario
principal está en `streamlit_app.py`.

## Ejecución y comprobación

Desde `practicas/01-estimador-cag/mi-proyecto`:

```powershell
uv sync --locked --dev
uv run --locked uvicorn app.main:app --reload
```

En otra terminal:

```powershell
uv run --locked streamlit run streamlit_app.py
```

Configuración y límites: [README del proyecto](mi-proyecto/README.md).
Las claves permanecen en `.env`, ignorado por Git. No se modificaron claves.

Para ejecutar toda la suite, sin levantar servidores ni configurar credenciales:

```powershell
uv run --locked python -m pytest -q
```

| Hito | Resultado local |
| --- | --- |
| Base de sesión 4 | 30 pruebas, registradas en su guía |
| Estructuras de sesión | 39 pruebas, incluidas nueve nuevas |
| Contrato y adaptadores | 49 pruebas, incluidas diez nuevas |
| Integración, documentos e interfaz | 71 pruebas y 139 subcasos |

Las pruebas de integración con AsyncClient verifican dos turnos con metadatos,
un PDF que cambia el coste devuelto por un proveedor simulado y ocho turnos
con ventana limitada. También cubren tablas Word, límites, corrupción,
sesión desconocida, aislamiento, peticiones simultáneas y conservación del
estado si falla el proveedor. AppTest comprueba tres turnos, panel de hechos,
nueva conversación, adjuntos múltiples y errores de interfaz.

La suite bloquea la red externa y los SDK reales. No se consumieron tokens.
En Windows, el aislamiento bloqueó inicialmente las pruebas asíncronas;
se ejecutaron con los permisos necesarios, como en la sesión anterior.
Al añadir `v2`, una prueba antigua que usaba esa versión como inexistente
se ajustó a `v999`. GitHub Actions usa ahora pytest para incluir también las
pruebas nuevas; pytest sigue ejecutando las unittest anteriores.

## Criterios de entrega

- [x] Crear y consultar sesiones UUID.
- [x] Estimación multipart con transcripción y adjuntos opcionales.
- [x] Historial limitado y metadatos separados, visibles en Streamlit.
- [x] Salida estructurada validada, sin romper los endpoints anteriores.
- [x] Botón de nueva conversación y prueba de tres turnos en la interfaz.
- [x] Pruebas locales, README operativo y dependencias bloqueadas.
- [x] Commit, push y verificación de GitHub Actions.

La captura/GIF opcional no se generó. La coherencia semántica y calidad de
un proveedor real siguen pendientes de una prueba autorizada con consumo de
tokens; las pruebas simuladas acreditan transporte y actualización del estado.

## Publicación

Commit de implementación: `c08c297b0ed67638f0cff19bf5b92f81f7638f2c`.
Se hizo `git push -u origin pre-session-05` y se verificó el seguimiento de
la rama remota sin cambios locales pendientes antes del cierre documental.

[GitHub Actions, ejecución 43108306039](https://github.com/juanzaldo/lidr-ai-engineer/actions/runs/43108306039)
terminó con `success`: instalación desde lockfile, comprobación de archivos
privados y suite de pruebas aprobadas. La verificación se realizó mediante
la API de GitHub el 11 de noviembre de 2026. Este cierre documental se publica
como commit adicional; no cambia la implementación validada.

Enlace de entrega:
[pre-session-05](https://github.com/juanzaldo/lidr-ai-engineer/tree/pre-session-05).
El envío a Sisley por correo o WhatsApp corresponde al usuario; no se ha enviado.

## Temas reservados para el directo

Compresión por resumen/anclas, tier dinámico, persistencia, búsqueda web,
function calling para BBDD y Actor-Critic-Boss. La caché propia exact-match
sigue siendo una carencia heredada que no bloquea este flujo: el maestro
tampoco usa cachés de respuesta en las conversaciones.

## Referencias técnicas consultadas

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
- [Herramientas de Anthropic](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools).
- [FastAPI: formularios y archivos](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/).
- [pypdf: extracción de texto](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).
- [python-docx: documentos](https://python-docx.readthedocs.io/en/latest/api/document.html).
- [HTTPX: transporte ASGI](https://www.python-httpx.org/advanced/transports/).
