# Guía de la práctica 01: estimador de software con CAG

Esta guía recoge el trabajo realizado el 20 de octubre de 2026 y sirve
como material para repetir la práctica en futuros cursos. Los resultados
registrados corresponden a las pruebas realizadas, no a garantías de calidad
de las estimaciones. Las claves reales no forman parte de esta guía.

## Objetivo y arquitectura

Recibir una transcripción por HTTP, incluir ejemplos estáticos en el prompt,
llamar a un LLM y devolver una estimación dentro de una respuesta JSON.

```text
Swagger o cliente HTTP
    → POST /api/v1/estimate
    → validación Pydantic
    → generate_estimation()
    → instrucciones + ejemplos estáticos + transcripción
    → OpenAI o Anthropic
    → JSON con estimación y metadatos
```

No hay base de datos, retrieval ni persistencia de solicitudes. El contexto
viaja en cada llamada. Elegimos CAG porque los pocos ejemplos de referencia
caben en la ventana de contexto y permiten comenzar sin infraestructura extra.

## Paso 1: requisitos, estructura y dependencias

En PowerShell verificamos:

```powershell
Get-Location
python --version
uv --version
```

La terminal reportó Python 3.14.3 y uv 0.12.23. El requisito del proyecto es
Python 3.11 o superior. La ejecución posterior de las pruebas mediante uv
utilizó Python 3.11.17: el Python del comando global y el del entorno del
proyecto pueden ser diferentes.

El proyecto se llamó `estimator-cag`, aunque el enunciado sugería
`estimador-cag`. Se inicializó con uv. La configuración obtenida incluía
`src/estimator_cag`, un comando de consola y un backend de construcción.
Retiramos los bloques `[project.scripts]` y `[build-system]` de
`pyproject.toml`, conservando `[project]`, y creamos:

```text
app/
├── __init__.py
├── main.py
├── config.py
├── routers/
│   ├── __init__.py
│   └── estimations.py
├── services/
│   ├── __init__.py
│   └── llm_service.py
└── context/
    ├── __init__.py
    └── examples.py
```

`routers` atiende HTTP, `services` gestiona la llamada al modelo y `context`
guarda los ejemplos estáticos. Después de revisar que `src` solo contenía
un saludo generado, retiramos ese archivo y sus carpetas vacías.

Creamos `.env` y `.env.example`. El primero se excluye de Git; el segundo
documenta las variables sin valores. Añadimos estas reglas a `.gitignore`:

```gitignore
.env
.env.*
!.env.example
```

Instalamos ambos proveedores:

```powershell
uv add fastapi "uvicorn[standard]" pydantic-settings python-dotenv
uv add openai anthropic
```

FastAPI define la API; Uvicorn la sirve; pydantic-settings carga y valida la
configuración; python-dotenv permite leer `.env`; los SDK conectan con cada
proveedor. uv registra dependencias y genera `uv.lock`, que se conserva en Git.

**Incidencia:** PowerShell mostraba `estimaciÃ³n`. Al ejecutar
`Get-Content pyproject.toml -Encoding UTF8`, los acentos se veían correctamente.
El archivo estaba bien guardado; no fue necesario reemplazar el texto.

## Paso 2: configuración

`app/config.py` define `Settings`, derivada de `BaseSettings`, y la instancia
`settings = Settings()`. Lee el `.env` de la raíz del proyecto en UTF-8.
Las variables de entorno tienen prioridad sobre el archivo.

| Variable | Valor predeterminado o condición |
|---|---|
| OPENAI_API_KEY | Requerida cuando se selecciona OpenAI |
| ANTHROPIC_API_KEY | Requerida cuando se selecciona Anthropic |
| LLM_PROVIDER | openai |
| LLM_MODEL | gpt-4o-mini |
| APP_ENV | development |
| LOG_LEVEL | DEBUG |

Las claves usan `SecretStr`; se valida la presencia de la clave del proveedor
seleccionado. Esto no confirma que la clave sea válida ni que haya créditos.
Las variables vacías se ignoran para aplicar los valores predeterminados.
LOG_LEVEL queda disponible como configuración; todavía no configura por sí
solo los handlers de logging.

Para Anthropic se cambian conjuntamente `LLM_PROVIDER=anthropic` y
`LLM_MODEL=claude-haiku-4-5`. Tener los dos SDK instalados no implica llamar
a ambos en cada solicitud.

Se indicó recuperar las claves existentes desde el panel de secretos de
Google Colab y copiarlas únicamente al `.env` local. No se compartieron
claves en la conversación.

Comprobación sin consumo de tokens:

```powershell
uv run python -c "from app.config import settings; print('Proveedor:', settings.LLM_PROVIDER); print('Modelo:', settings.LLM_MODEL)"
```

Resultado confirmado: `openai` y `gpt-4o-mini`.

**Incidencia:** apareció `ImportError: cannot import name 'settings'`.
El código compartido sí contenía la instancia; después de guardar el archivo
y repetir la ejecución, la importación funcionó. Una versión sin guardar
fue la causa probable, no una causa demostrada.

## Paso 3: ejemplos estáticos

`ESTIMATION_EXAMPLES` contiene referencias ficticias para inventario y
reservas. Cada una incluye `meeting_summary` y `estimation`, con tareas,
horas, costes, supuestos, contingencia, equipo, duración y exclusiones.

Usamos una tarifa didáctica de 500 MXN/hora, no una recomendación de mercado.
Los ejemplos enseñan formato y razonamiento; sus horas no deben copiarse
automáticamente a cualquier solicitud. Las pruebas automáticas verifican
que haya al menos dos y que sus textos se incluyan en el prompt.

## Paso 4: servicio LLM

**El corazón de CAG está en `build_system_prompt()`:** incorpora todos los ejemplos en cada llamada. No consulta bases de datos ni realiza búsquedas.

En OpenAI, las instrucciones viajan como mensaje `system`; en Anthropic se pasan mediante el parámetro `system`. El significado es el mismo, aunque cambie la interfaz. Referencias: [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) y [SDK de Anthropic](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python).

La función devuelve **texto Markdown**; cuando implementemos el endpoint, lo incluiremos dentro de la respuesta JSON. Usamos `async` para que la espera del proveedor pueda integrarse con un endpoint asíncrono de FastAPI.

El párrafo anterior conserva la explicación original del paso 4. Al ampliar
el paso 5, la función evolucionó para devolver un diccionario: el texto
Markdown quedó en `estimation`, acompañado de metadatos.

Utilizamos AsyncOpenAI y AsyncAnthropic. La transcripción viaja como mensaje
de usuario y el prompt pide tratarla como datos, declarar supuestos y revisar
totales. Se rechazan entradas vacías, respuestas vacías y terminaciones
incompletas. Los errores del proveedor aún no tienen una traducción HTTP
personalizada: es una mejora pendiente.

La primera prueba real estimó una aplicación de tareas para diez personas.
Funcionó con OpenAI. Su salida se conserva en
`mi-proyecto/app/results/Session 2SalidaPaso4.md`.

## Paso 5: endpoint y metadatos

`POST /api/v1/estimate` recibe un objeto con `transcription`. Pydantic valida
el campo y rechaza espacios sin contenido con HTTP 422 antes de llamar al
servicio. Postman, curl o Swagger llaman a nuestra API; el endpoint llama
directamente a la función Python usando `await`.

La respuesta contiene `estimation`, `model`, `provider`, `input_tokens`,
`output_tokens`, `total_tokens`, `estimated_cost_usd`, `timestamp` y
`latency_ms`. Los tokens proceden del proveedor. El modelo reportado puede
incluir una versión concreta. El timestamp es UTC; la latencia mide la
espera del servicio, no el tiempo completo desde el navegador.

El coste se calcula localmente con tarifas de referencia. No es el coste
del proyecto de software ni una factura del proveedor. Para modelos sin
tarifa registrada devuelve null. Se desactivaron los reintentos automáticos
en esta versión de la práctica. No se solicita caché a Anthropic.

## Paso 6: FastAPI

`main.py` crea la aplicación con título y descripción, registra el router
y define `GET /health`, que devuelve `{"status": "ok"}`.
El prefijo `/api/v1` ya está en el router y no se duplica al registrarlo.
`/health` comprueba que la aplicación responde; no valida las claves ni
consulta al LLM.

## Paso 7: arranque y verificación desde Swagger

Desde la carpeta del proyecto:

```powershell
uv run uvicorn app.main:app --reload
```

| Parte | Función |
|---|---|
| uv run | Ejecuta en el entorno del proyecto sin activarlo manualmente |
| uvicorn | Servidor ASGI que recibe HTTP y lo entrega a FastAPI |
| app.main | Módulo Python correspondiente a app/main.py |
| :app | Variable que contiene la instancia FastAPI |
| --reload | Reinicio automático al cambiar código durante desarrollo |

El proceso se mantiene abierto; Ctrl + C lo detiene. Arrancarlo no consume
tokens. Se abrió http://127.0.0.1:8000/docs y se probó con Try it out → Execute.

Resultados confirmados por el usuario:

- `/health`: respuesta `{"status": "ok"}`.
- Transcripción vacía: HTTP 422.
- Transcripción válida de landing page, HubSpot y blog: estimación generada.
- Modelo: `gpt-4o-mini-2024-07-18`; proveedor: OpenAI.
- Entrada: 1282 tokens; salida: 493; total: 1775.
- Coste estimado: 0.0004881 USD; latencia: 5592 ms.
- Timestamp: `2026-10-21T01:06:48.713067Z`, equivalente a las 19:06:48
  del 20 de octubre en Ciudad de México.

La transcripción reproducible está en `transcripcion-reunion.txt`.
No se exige que una nueva llamada genere idéntico texto.

## Precios y calidad del resultado

Tarifas consultadas el 20 de octubre de 2026, USD por millón de tokens:

| Modelo | Entrada | Lectura de caché | Salida |
|---|---:|---:|---:|
| gpt-4o-mini | 0.15 | 0.075 | 0.60 |
| claude-haiku-4-5 | 1.00 | 0.10 | 5.00 |

- [Precios de GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [Precios de Anthropic y tarifas adicionales de escritura de caché](https://platform.claude.com/docs/en/about-claude/pricing)

El ejemplo registrado: `(1282 × 0.15 + 493 × 0.60) / 1000000 = 0.0004881 USD`.
Consultar las fuentes al repetir el curso porque las tarifas pueden cambiar.

La primera estimación redondeó el 20% de 172 horas a 34; el valor exacto
es 34.4. La segunda redondeó el 20% de 104 a 21 horas sin explicarlo y
propuso 125 horas en cuatro semanas con 30 horas semanales: esa capacidad
solo suma 120 horas. El flujo técnico funciona, pero la calidad necesita
revisión humana. Una mejora sería calcular totales con Python y validar
coherencia de esfuerzo, equipo y plazo.

## Organización del repositorio

Se creó https://github.com/juanzaldo/lidr-ai-engineer y se clonó en una carpeta
independiente del proyecto original. La implementación se copió a
`practicas/01-estimador-cag/mi-proyecto`, excluyendo `.env`, `.venv`, `.git`
y cachés. Se confirmó con Test-Path que `.env` y `.git` internos no se copiaron.
La plantilla `.env.example` se copió explícitamente. El original se conserva.

La solución del curso está en
https://github.com/LIDR-academy-temp/ai-engineering/tree/session_2.
Su incorporación y comparación siguen pendientes de revisar contenido y licencia.
Los intentos iniciales de acceso desde la terminal fallaron por resolución de
github.com; no se concluyó que el repositorio fuera inválido o privado.

Se añadieron README del curso y de la práctica, transcripción y documentación.
El repositorio raíz gestiona todas las lecciones: no se requieren repositorios
Git anidados dentro de cada práctica.

## Pipeline de validación automática

Un pipeline ejecuta comprobaciones al subir cambios. El archivo
`.github/workflows/validate.yml` configura GitHub Actions para push, pull
request y ejecución manual. Instala dependencias bloqueadas, revisa exclusión
de archivos privados y ejecuta siete pruebas con unittest y TestClient.

La función LLM se sustituye por AsyncMock. Se usan claves ficticias y se
bloquean los transportes HTTP externos. No se consumen tokens. Se prueba
estructura, plantilla, inclusión de ejemplos, salud, entrada inválida,
respuesta JSON y documentación. Esto no prueba la conexión real a los SDK.

```powershell
uv sync --locked --dev
uv run --locked python -m unittest discover -s tests -v
```

Las siete pruebas pasaron localmente con Python 3.11.17. Se validó también
la sincronización del lockfile y la sintaxis YAML. La primera ejecución
remota queda pendiente del primer push. Más detalle en
[validacion-automatica.md](validacion-automatica.md).

## Estado y siguientes mejoras

- Flujo funcional y prueba real con OpenAI: completados.
- Pruebas automáticas locales: aprobadas.
- Prueba real con Anthropic: pendiente, para evitar gasto adicional.
- Publicación y primera ejecución de Actions: pendientes.
- Solución oficial y comparación: pendientes.
- Mejoras futuras: manejo HTTP de errores del proveedor, pruebas del servicio,
  cálculos deterministas, refinamiento del prompt y comparación entre modelos.
