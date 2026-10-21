# Estimador CAG — mi implementación

API FastAPI con contexto estático y selección entre OpenAI y Anthropic.

- [Preparación y prueba desde Swagger](../README.md)
- [Guía de la práctica](../guia-practica.md)
- [Validación automática](../validacion-automatica.md)

Desde esta carpeta, instala las dependencias con `uv sync --locked`,
crea tu `.env` a partir de `.env.example` y configura las claves localmente.
Arranca con `uv run uvicorn app.main:app --reload`.

Las pruebas sin consumo de tokens se ejecutan con:

```powershell
uv run --locked python -m unittest discover -s tests -v
```
