# Validación automática de la práctica 01

Un pipeline es una secuencia de comprobaciones que GitHub ejecuta al subir
cambios. El workflow está en `.github/workflows/validate.yml` y se activa
con push, pull request o manualmente desde la pestaña Actions.

## Qué hace

1. Descarga el repositorio en un entorno temporal Linux.
2. Instala uv 0.12.23 y Python 3.11, la versión mínima del proyecto.
3. Ejecuta `uv sync --locked --dev`: instala las versiones del lockfile y
   falla si este no concuerda con `pyproject.toml`.
4. Comprueba que no haya archivos `.env` ni `.venv` registrados en Git,
   que `.env` esté ignorado y que `.env.example` pueda compartirse.
5. Ejecuta las pruebas con unittest y TestClient de FastAPI.

Las comprobaciones revisan la estructura, la plantilla de configuración,
los ejemplos presentes en el prompt, `/health`, Swagger/OpenAPI, entradas
inválidas y una respuesta JSON con los metadatos esperados.

## Sin consumo de tokens

Las pruebas usan claves ficticias y sustituyen `generate_estimation` en
el router por un `AsyncMock`. La entrada válida devuelve datos conocidos;
las entradas inválidas deben rechazarse antes de llamar al servicio.
También se bloquean los transportes HTTP externos usados por httpx.
No hacen falta secretos de OpenAI o Anthropic en GitHub Actions.

Estas pruebas verifican la aplicación y su contrato HTTP, pero no la
disponibilidad de los proveedores, la exactitud de las tarifas ni la calidad
de una estimación real. El servicio LLM se sustituye, por lo que no se
prueba aquí la integración de sus SDK. Las pruebas reales siguen siendo
una comprobación separada desde Swagger.

## Ejecutar localmente

Desde la raíz del repositorio, en PowerShell:

```powershell
cd practicas/01-estimador-cag/mi-proyecto
uv sync --locked --dev
uv run --locked python -m unittest discover -s tests -v
```

No necesitas arrancar Uvicorn ni crear `.env` para estas pruebas.
TestClient envía peticiones a la aplicación dentro del mismo proceso.
`httpx` se declara como dependencia de desarrollo; unittest viene con Python.

## Leer el resultado en GitHub

Después del push, abre Actions y el workflow «Validar practica 01».
Verde significa que pasaron las comprobaciones; rojo indica un fallo.
Abre el paso fallido para consultar el mensaje. Un fallo no revierte el push.
Para impedir merges con pruebas fallidas se requieren reglas de rama,
que esta práctica todavía no configura.

## Fuentes

- [Pruebas de FastAPI](https://fastapi.tiangolo.com/tutorial/testing/)
- [uv en GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/)

## Bitácora

- Se añadieron pruebas sin llamadas reales al LLM.
- Se declaró httpx como dependencia de desarrollo y se actualizó uv.lock.
- Se creó el workflow y se actualizaron los README.
- Verificación local: siete pruebas aprobadas con Python 3.11.17, sin
  llamadas al LLM. El entorno aislado bloqueó inicialmente la comunicación
  interna de asyncio en Windows; fuera de ese aislamiento las pruebas pasaron.
- La primera ejecución en GitHub está pendiente del primer push.
