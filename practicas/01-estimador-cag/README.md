# Práctica 01 — Estimador de software con CAG

## Objetivo

Construir una API FastAPI que reciba la transcripción de una reunión
y devuelva una estimación de software generada por un LLM.

## Flujo

Transcripción → endpoint FastAPI → instrucciones y ejemplos estáticos
→ llamada al LLM → respuesta JSON.

El contexto se incluye directamente en cada petición al modelo.
No utilizamos base de datos, búsqueda de documentos ni persistencia.

## Contenido

- `mi-proyecto/`: implementación desarrollada durante la práctica.
- `transcripcion-reunion.txt`: entrada de ejemplo para las pruebas.
- [guia-practica.md](guia-practica.md): pasos, decisiones, errores y resultados registrados.
- `solucion-referencia/`: copia de la solución del curso en la rama session_2.
- [REFERENCIA.md](REFERENCIA.md): procedencia, commit y comparación de ambas implementaciones.

## Requisitos

- Python 3.11 o superior.
- uv instalado.
- Una API key del proveedor seleccionado y créditos disponibles.

## Preparación

Desde la raíz del repositorio:

```powershell
cd practicas/01-estimador-cag/mi-proyecto
uv sync --locked
Copy-Item .env.example .env
```

El comando de copia es para la primera configuración.
Si ya tienes un `.env`, edítalo sin sobrescribirlo.

Completa `.env` localmente con la clave del proveedor elegido.

Para OpenAI:

```dotenv
OPENAI_API_KEY=TU_CLAVE_REAL
ANTHROPIC_API_KEY=
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
APP_ENV=development
LOG_LEVEL=DEBUG
```

Para Anthropic, configura `ANTHROPIC_API_KEY` y cambia:

```dotenv
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-4-5
```

No subas `.env` al repositorio.

## Arranque

Desde `mi-proyecto/`:

```powershell
uv run uvicorn app.main:app --reload
```

- `uv run`: ejecuta dentro del entorno del proyecto.
- `uvicorn`: servidor que atiende las peticiones HTTP.
- `app.main`: módulo correspondiente a `app/main.py`.
- `:app`: variable que contiene la aplicación FastAPI.
- `--reload`: reinicia el servidor al detectar cambios durante el desarrollo.

Para detener el servidor, pulsa Ctrl + C.

## Prueba desde Swagger

Abre http://127.0.0.1:8000/docs.

1. Ejecuta `GET /health`: debe responder 200 y `{"status": "ok"}`.
2. Ejecuta `POST /api/v1/estimate` con una transcripción de espacios:
   debe responder 422 sin llamar al proveedor.
3. Ejecuta el mismo endpoint usando el contenido de
   `transcripcion-reunion.txt` dentro del campo `transcription`.

Ejemplo de entrada:

```json
{
  "transcription": "Necesitamos una landing page con formulario de contacto."
}
```

La respuesta incluye:

- `estimation`: estimación en texto Markdown.
- `model` y `provider`: modelo y proveedor utilizados.
- `input_tokens`, `output_tokens` y `total_tokens`: uso reportado.
- `estimated_cost_usd`: coste aproximado de la llamada al LLM.
- `timestamp`: fecha y hora UTC.
- `latency_ms`: tiempo transcurrido de la llamada.

Arrancar el servidor, consultar Swagger y ejecutar `/health` no consume
tokens del LLM. Generar una estimación sí consume créditos.

## Verificación registrada

La implementación original se probó localmente:

- `/health` devolvió `{"status": "ok"}`.
- Una transcripción vacía devolvió 422.
- Una transcripción válida produjo una estimación mediante OpenAI.
- La respuesta incluyó tokens, coste estimado, timestamp y latencia.

La prueba real con Anthropic queda pendiente.
El pipeline automatizado está definido en `.github/workflows/validate.yml`.
La primera ejecución en GitHub queda pendiente del primer push.
Consulta [cómo ejecutar y entender las pruebas](validacion-automatica.md).

## Limitaciones

La estimación requiere revisión humana. Se observaron redondeos de
contingencia sin explicación y discrepancias entre esfuerzo y plazo.

El coste de la llamada al LLM es distinto del coste del proyecto
de software descrito en la estimación.

## Fuentes de precios

Tarifas consultadas el 20 de octubre de 2026, expresadas en USD
por millón de tokens:

| Modelo | Entrada | Entrada en caché | Salida |
|---|---:|---:|---:|
| gpt-4o-mini | 0.15 | 0.075 | 0.60 |
| claude-haiku-4-5 | 1.00 | 0.10 | 5.00 |

La implementación actual no solicita caché a Anthropic.
La escritura de caché tiene tarifas adicionales que deben contemplarse
si se incorpora esa funcionalidad.

- [OpenAI: GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [Anthropic: precios](https://platform.claude.com/docs/en/about-claude/pricing)

Las tarifas pueden cambiar. El cálculo local es orientativo y no
sustituye la facturación del proveedor.

## Solución del curso

[Repositorio de referencia, rama session_2](https://github.com/LIDR-academy-temp/ai-engineering/tree/session_2)

Incorporada desde el commit `79e49374f04652f0b8b62c13b9783ab13b226e6f`.
No se encontró un archivo de licencia en esa versión. Consulta
[la procedencia y condiciones pendientes](REFERENCIA.md).
