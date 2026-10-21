# Procedencia y comparación de la solución

## Origen

- Autoría: repositorio del curso LIDR Academy.
- Repositorio: https://github.com/LIDR-academy-temp/ai-engineering
- Rama: `session_2`.
- Commit: `79e49374f04652f0b8b62c13b9783ab13b226e6f`.
- Carpeta original: `estimator/`.
- Destino: `solucion-referencia/`.
- [Ver versión exacta](https://github.com/LIDR-academy-temp/ai-engineering/tree/79e49374f04652f0b8b62c13b9783ab13b226e6f/estimator).

Se copiaron los 22 archivos registrados en Git de esa carpeta sin modificar
su contenido. Se comprobó la igualdad de hashes SHA-256 con la copia local
de origen. No se incorporaron `.git`, `.env` real ni entornos virtuales.

No se encontró LICENSE ni COPYING en la versión revisada. Se conserva la
atribución; esta documentación no concede una licencia sobre el código de
terceros ni afirma que sea libremente redistribuible. Consultar las condiciones
del curso antes de redistribuirlo fuera del acceso autorizado.

## Diferencias observadas en el código

| Aspecto | Mi proyecto | Solución del curso |
|---|---|---|
| Proveedores | OpenAI y Anthropic | OpenAI y Anthropic |
| Llamadas al LLM | SDK asíncrono con await | SDK síncrono invocado desde endpoint async |
| Schemas | En el módulo del router | Separados en app/schemas/estimation.py |
| Entrada | Recorta espacios y rechaza contenido vacío | Exige longitud mínima de 50 caracteres |
| Uso de tokens | Campos en la raíz del JSON | Objeto usage |
| Metadatos adicionales | Coste USD, timestamp UTC y latencia | Sin esos tres campos |
| Configuración | Instancia settings; claves SecretStr | get_settings con lru_cache; claves str |
| Errores del proveedor | Sin traducción HTTP personalizada | LLMServiceError convertido a HTTP 500 |
| Logging | Configuración LOG_LEVEL disponible | structlog y eventos de inicio/cierre |
| Health | status: ok | status: healthy, version y environment |
| Prompt | Español; tarifa ficticia uniforme de 500 MXN/h | Inglés; tarifas de desarrollo y diseño en EUR |
| Ejecución | uv local | Docker/Compose y alternativa uv local |
| Pruebas | Siete pruebas unittest con LLM simulado | Una prueba pytest de health |
| Dependencias | uv.lock incluido | Sin uv.lock en el commit revisado |

La comparación se basa en lectura del código. La referencia no se ha
ejecutado ni se han hecho llamadas a sus proveedores. No se mezclan ambas
implementaciones. El pipeline actual valida únicamente `mi-proyecto/`.

## Cómo comparar

Revisar primero los mismos módulos dentro de las dos carpetas:

1. `app/config.py`: configuración y validación.
2. `app/services/llm_service.py`: prompt, proveedores y errores.
3. `app/routers/estimations.py`: contrato HTTP y llamadas al servicio.
4. `app/main.py`: arranque y health.
5. `tests/`: alcance de las pruebas.

Para ver las diferencias textuales desde la carpeta de la práctica:

```powershell
git diff --no-index -- mi-proyecto/app solucion-referencia/app
```

Este comando no cambia archivos; devuelve código 1 cuando encuentra diferencias.
Si se prueban ambas aplicaciones, ejecutarlas por separado o utilizar puertos
distintos para evitar que compitan por el puerto 8000.
