# Sesión 3: interfaz conversacional del estimador CAG

Continuamos el proyecto de la sesión 2 en la rama `session_3`. Conservamos
la misma carpeta `mi-proyecto` porque es una evolución del mismo servicio.
La entrega anterior permanece en su rama y commit anteriores.

## 1. Preparar el entorno

Abrimos el repositorio en VS Code, seleccionamos la rama `session_3` y el
intérprete `mi-proyecto/.venv/Scripts/python.exe`. Añadimos Streamlit con
`uv add streamlit`; las dependencias quedaron registradas en `pyproject.toml`
y `uv.lock`. Para reproducir la instalación usamos `uv sync --locked --dev`.

Los comandos siguientes se ejecutan dentro de `practicas/01-estimador-cag/mi-proyecto`.
Copiamos `.env.example` a `.env` y completamos las claves localmente.
Nunca se publica `.env`. OpenAI es el proveedor inicial predeterminado.

## 2. Construir el chat

Creamos `streamlit_app.py` en la raíz del proyecto. `st.chat_input` recibe
la transcripción, `st.chat_message` dibuja los mensajes y `st.session_state`
guarda el historial durante la sesión del navegador. Streamlit vuelve a
ejecutar el script al interactuar; por eso inicializamos el historial solo
una vez y recalculamos sus totales sin incrementar contadores en cada rerun.

El historial visible no se envía al LLM: cada estimación utiliza la nueva
transcripción y el contexto CAG. Cambiar de modelo conserva los mensajes,
pero no implica que un modelo conozca las respuestas del otro.

## 3. Reutilizar CAG y añadir streaming

**El corazón de CAG está en `build_system_prompt()`:** incorpora todos los
ejemplos en cada llamada. No consulta bases de datos ni realiza búsquedas.
En OpenAI las instrucciones viajan como mensaje `system`; en Anthropic se
pasan mediante el parámetro `system`.

Las funciones `stream_estimation_openai` y `stream_estimation_anthropic`
emiten eventos de texto a medida que llegan y un resultado final con métricas.
`st.write_stream` muestra el texto progresivamente. Los fragmentos recibidos
pueden contener varios tokens: no son necesariamente un token por evento.

Streamlit llama directamente al servicio Python compartido. No necesita
arrancar FastAPI ni pasar por HTTP. FastAPI continúa disponible para clientes
REST y Swagger. El resultado es Markdown; el endpoint REST lo envuelve en JSON.

## 4. Selector y consumo

Añadimos un selector con `gpt-4o-mini` y `claude-haiku-4-5`, los modelos
económicos elegidos para la práctica. Cada función admite `requested_model`
y utiliza su modelo predeterminado si no se proporciona uno. Añadir modelos
al selector exige revisar también sus tarifas y compatibilidad de parámetros.

Cada respuesta guarda su proveedor, modelo, tokens de entrada/salida y costes
estimados. El acumulado suma únicamente las respuestas completadas con métricas.
Cambiar de modelo o redibujar la página no duplica el consumo. Una llamada
fallida puede generar cargos aunque no quede incluida en ese acumulado.
El historial y los totales no son persistentes ni representan el saldo de la cuenta.

La entrada incluye instrucciones, ejemplos y transcripción. El cálculo de OpenAI
distingue entrada cacheada. Para Anthropic, si hay uso de caché sin una tarifa
implementada, el coste se muestra como no disponible, no como cero.

Tarifas de referencia de la práctica, USD por millón de tokens:

| Modelo | Entrada | Entrada cacheada | Salida |
| --- | ---: | ---: | ---: |
| gpt-4o-mini | 0.15 | 0.075 | 0.60 |
| claude-haiku-4-5 | 1.00 | No calculada en este flujo | 5.00 |

Son estimaciones basadas en tarifas registradas durante el ejercicio, no una
consulta en vivo de facturación. Consultar las tarifas vigentes antes de cambiarlas:
[OpenAI](https://openai.com/api/pricing/) y
[Anthropic](https://platform.claude.com/docs/en/about-claude/pricing).

## 5. Diagnosticar Anthropic

El SDK instalado rechazó `temperature` en streaming. Retiramos ese argumento
de las llamadas Anthropic y conservamos los valores predeterminados del proveedor.
Después recibimos HTTP 400: la clave no estaba asociada a un workspace.
El diagnóstico específico permitió distinguir este problema de un error de modelo.

Añadimos `ANTHROPIC_WORKSPACE_ID` opcional a la configuración y a `.env.example`.
Cuando tiene valor, ambos clientes Anthropic envían la cabecera
`anthropic-workspace-id`. Se obtiene el ID en
[Workspaces](https://platform.claude.com/settings/workspaces) y se añade a `.env`:

```dotenv
ANTHROPIC_WORKSPACE_ID=wrkspc_TU_ID
```

Reiniciar Streamlit después de cambiar `.env`, porque la configuración se carga
al importar el módulo. Las claves ligadas a un workspace pueden dejar este campo vacío.
[Documentación de workspaces](https://platform.claude.com/docs/en/manage-claude/workspaces).

## 6. Panel opcional y ejecución

El panel lateral contiene el prompt activo completo en modo lectura, los ejemplos
de referencia, el proveedor/modelo y los tokens y tiempo de la última llamada
completada, además de los totales de sesión. La latencia mide la generación
completa, no el tiempo hasta el primer token.

```powershell
uv run streamlit run streamlit_app.py
```

Abrir la dirección local que indique Streamlit (normalmente http://localhost:8501).
Pegar `../transcripcion-reunion.txt` o el ejemplo de cafetería en `app/extimacion.txt`.
Observar la generación progresiva, enviar otra transcripción y cambiar de proveedor.
Se necesitan las claves y el acceso correspondiente para una prueba real de ambos.

Para ejecutar la API por separado:

```powershell
uv run uvicorn app.main:app --reload
```

`uv run` usa el entorno del proyecto; `uvicorn` es el servidor ASGI;
`app.main:app` identifica el módulo y la instancia FastAPI; `--reload`
reinicia al cambiar archivos y se utiliza durante desarrollo.
Swagger: http://localhost:8000/docs. Salud: http://localhost:8000/health.

## 7. Validación y entrega

```powershell
uv run --locked python -m unittest discover -s tests -v
```

Las pruebas simulan los proveedores para no gastar tokens. Cubren API, validación,
contexto, errores, logging y la interfaz: cambio de proveedor, conservación del
historial, acumulados sin duplicados, métricas y bloqueo si falta la clave.
GitHub Actions ejecuta el mismo descubrimiento de pruebas en cada push.
Las pruebas simuladas no confirman créditos ni permisos reales de los proveedores.

Resultado local del 28 de octubre de 2026: 15 pruebas aprobadas, sin llamadas
reales a los LLM durante la validación automática.

Los niveles 1 y 2 están implementados, junto con el panel opcional del nivel 3.
La publicación de esta evolución en `session_3` fue autorizada el 28 de octubre
de 2026. La referencia del curso se conserva sin cambios.

Enlace de entrega: https://github.com/juanzaldo/lidr-ai-engineer/tree/session_3
Enviar personalmente al facilitador indicando sesión 3; si el repositorio es
privado, dar acceso a `SisleyInTech`. Esta tarea no envía correos ni cambia accesos.
