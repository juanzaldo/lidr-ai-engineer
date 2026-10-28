# Mejoras posteriores a la entrega original

Actualización del 28 de octubre de 2026: se autoriza incluir estas mejoras en
`session_3`. El texto siguiente conserva el registro de la etapa local previa.
La continuación se documenta en [guia-session-3.md](guia-session-3.md).

Por indicación del usuario, estas mejoras no deben publicarse hasta que lo
autorice. La versión entregada está en el commit
`15d531d723d6774c06628616b0236860e7743943`. En esta iteración no se hizo
commit ni push. La solución de referencia se conserva intacta.

## Conceptos: LRU, ASGI y asincronía

LRU significa Least Recently Used (usado menos recientemente). `lru_cache`
guarda resultados de una función según sus argumentos para reutilizarlos.
Si se alcanza el límite de entradas, descarta las menos usadas recientemente.
En la referencia, `get_settings()` no recibe argumentos: conserva una sola
configuración y evita reconstruirla en cada llamada. Cambiar `.env` no la
actualiza automáticamente; normalmente se reinicia el proceso.

Nuestra configuración sigue usando la instancia `settings = Settings()`.
No se añadió lru_cache: la instancia ya se reutiliza en el proceso.

ASGI significa Asynchronous Server Gateway Interface. Es la interfaz entre
el servidor Uvicorn y nuestra aplicación FastAPI. Uvicorn recibe las
peticiones HTTP; FastAPI decide qué endpoint ejecutar.

Una función `async def` puede ceder el control al llegar a un `await` que
espera una operación de entrada/salida. Así, mientras esperamos al LLM,
el bucle de eventos puede atender otras tareas. No acelera al modelo y no
convierte automáticamente una función síncrona en no bloqueante.

## Cambios implementados

1. Los modelos de entrada, salida y error viven en `app/schemas/estimation.py`.
   El router conserva la ruta y la validación de contenido vacío.
2. `_call_openai()` y `_call_anthropic()` aíslan las diferencias de cada SDK.
   `generate_estimation()` selecciona proveedor, normaliza errores y añade
   timestamp y latencia. Se conserva el prompt, la asincronía, los metadatos
   y las tarifas de la implementación original.
3. `app/logging_config.py` configura logging estándar de Python, sin añadir
   dependencias. Emite JSON, respeta LOG_LEVEL y evita handlers duplicados.
   El lifespan registra arranque y cierre; el servicio registra inicio,
   éxito o fallo de estimación. No incluye transcripciones, claves, prompts
   ni mensajes sin filtrar de excepciones. Los loggers de Uvicorn y de los
   SDK conservan su configuración propia.
4. `LLMServiceError` ofrece códigos y mensajes públicos controlados. El router
   decide el estado HTTP; el servicio no depende de FastAPI.

| Situación | HTTP | Código |
|---|---:|---|
| Tiempo de espera del proveedor | 504 | provider_timeout |
| Conexión, límite de uso/cuota o error 5xx del proveedor | 503 | provider_unavailable |
| Rechazo del proveedor, por ejemplo autenticación | 502 | provider_rejected |
| Respuesta vacía o incompleta | 502 | invalid_response |
| Configuración incorrecta del servicio | 500 | configuration_error |
| Error interno inesperado | 500 | internal_error |

Un 503 no garantiza que reintentar funcione: una cuota agotada puede requerir
revisar créditos. No se añadieron reintentos automáticos.

La entrada inválida sigue devolviendo el error de validación 422 de FastAPI.
Los errores del servicio devuelven este formato:

```json
{
  "detail": {
    "code": "provider_timeout",
    "message": "El proveedor tardó demasiado en responder."
  }
}
```

Swagger documenta los errores 500, 502, 503 y 504 además de la respuesta exitosa.

## Verificación local

Se ejecutaron 14 pruebas con éxito, usando respuestas SDK y errores simulados.
Se cubren ambos proveedores, transporte del prompt y transcripción, cálculo
de coste, cierre de clientes, respuestas vacías/truncadas, códigos HTTP y
ausencia de texto privado en mensajes públicos y logs. Se conserva la prueba
del contrato JSON exitoso. No se consumieron tokens ni se usaron claves reales.

```powershell
uv run --locked python -m unittest discover -s tests -v
```

No se realizaron nuevas pruebas reales con OpenAI o Anthropic. El pipeline
remoto no valida estos cambios hasta que se autorice publicarlos.

Fuente consultada para errores de SDK:
[OpenAI: error codes](https://developers.openai.com/api/docs/guides/error-codes).
