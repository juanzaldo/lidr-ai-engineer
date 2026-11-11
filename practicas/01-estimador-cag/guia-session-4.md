# Guía de la sesión 4 · Estimador CAG

## Punto de partida y autorización

El 4 de noviembre verificamos el repositorio personal en `session_3` y localizamos
`origin/session_4` en el clon del maestro. El 11 de noviembre de 2026 se autorizó
completar las modificaciones y subir el ejercicio. Creamos `pre-session-04`
desde `session_3` y trabajamos en `practicas/01-estimador-cag/mi-proyecto`.
Consultamos el loader y el router de la referencia local del maestro.

La implementación personal utilizaba Streamlit con llamadas directas al servicio
Python, proveedores OpenAI y Anthropic, streaming y logging JSON mediante
`logging`. Esa base registraba los tokens cacheados por el proveedor, pero
carecía de una caché propia exact-match de respuestas. El alcance de esta entrega
es el formulario, el contrato tipado, los templates versionados y sus pruebas.

## Qué cambió y cómo funciona

1. El formulario reúne descripción, tipo de proyecto, nivel de detalle y formato.
   Pydantic valida los valores en el cliente y nuevamente en FastAPI.
2. Streamlit hace `POST /estimate` con los cuatro campos como JSON.
3. El endpoint llama a `render_estimation_prompt(request, version="v1")`.
4. Jinja2 carga `system.j2`, `user.j2` y `examples.j2` desde `estimation/v1/`.
5. El servicio existente recibe las instrucciones y el proyecto por separado.
   OpenAI recibe roles `system` y `user`. Anthropic recibe el parámetro `system`
   y un mensaje `user`.
6. La API devuelve `text` y `prompt_version`. Streamlit muestra la estimación
   y conserva los resultados durante la sesión del navegador.

## Contrato y decisiones

Los modelos se añadieron al paquete existente `app/schemas/estimation.py`.
`EstimationRequest` exige una descripción de 20 a 2000 caracteres y tres enums
con los valores exactos del enunciado. También rechazamos descripciones que
alcanzan el mínimo únicamente mediante espacios. Conservamos el contenido
literal de la descripción en el bloque `<project_description>`.

El nuevo formulario usa el proveedor y modelo configurados en el backend.
Se configuran mediante `LLM_PROVIDER` y `LLM_MODEL` en `.env`. Ahora se necesitan
dos procesos, FastAPI y Streamlit. Los comandos están en el README del proyecto.

La ruta previa `/api/v1/estimate` conserva su contrato de transcripción y métricas
para los clientes anteriores, y aparece como obsoleta en Swagger. El formulario
nuevo utiliza `/estimate`, con el contrato solicitado en el ejercicio.
Las funciones de streaming de la sesión 3 conservan su interfaz Python.
Su prompt anterior se extrajo a `app/prompts/legacy/system.j2`.

## Prompts y versionado

`system.j2` contiene el rol, las instrucciones y las condiciones por formato y
nivel de detalle. Incluye `examples.j2`, con dos casos ficticios de préstamo de
equipo audiovisual y consolidación diaria de ventas. Los ejemplos también
adaptan su presentación al formato solicitado para evitar instrucciones
contradictorias. `user.j2` delimita los datos del proyecto.

El loader emplea `StrictUndefined`, `trim_blocks=True` y `lstrip_blocks=True`.
Una variable ausente provoca un error visible. Jinja2 interpola la descripción
como dato, conservando caracteres como `<`, `&` o `{{ datos }}`.

La carpeta `v1/` identifica una versión reproducible del comportamiento.
Para experimentar con otro prompt se crea `v2/` y se cambia `PROMPT_VERSION`
en el router. La firma del loader ya acepta esa versión. Una versión inexistente
produce un error y permite detectar una configuración equivocada.

## Por qué estas decisiones ayudan

El formulario limita las decisiones a los parámetros relevantes del estimador
y permite detectar entradas inválidas antes de consumir tokens. Las opciones
en español se serializan con los valores estables que espera la API.

Los archivos Jinja2 permiten revisar cambios de redacción, condiciones y ejemplos
en Git. La versión devuelta identifica el conjunto de instrucciones aplicado.
Los tests verifican el texto construido y las condiciones. La calidad y exactitud
de las estimaciones requieren evaluación con respuestas reales del modelo.

## Validación realizada

El 11 de noviembre pasaron 30 pruebas locales en 2.715 segundos con proveedores
simulados. Se verificaron las 36 combinaciones de los enums, la descripción
literal, el include de ejemplos, las instrucciones de formato y detalle,
variables ausentes, validación HTTP, errores del proveedor, mensajes separados,
compatibilidad de la API anterior y funcionamiento del formulario con AppTest.
Las seis pruebas específicas de templates pasaron en 28 milisegundos.

GitHub Actions aprobó la validación del commit `10052fd7af341efe99bc35cdb0c7154c8611f67c`.
Ejecución verificada el 11 de noviembre de 2026 en
https://github.com/juanzaldo/lidr-ai-engineer/actions/runs/43093038559.

Se añadieron Jinja2 y HTTPX como dependencias directas y se actualizó `uv.lock`.
La ejecución inicial quedó detenida dentro del aislamiento de Windows.
La misma suite pasó al ejecutarse con los permisos necesarios para TestClient.

La revisión automática de permisos rechazó una prueba con el proveedor real
porque habría consumido tokens de la cuenta y enviado el proyecto ficticio al
proveedor. La prueba real queda pendiente de autorización específica.

## Entrega

Rama publicada y verificada en GitHub el 11 de noviembre de 2026 en
https://github.com/juanzaldo/lidr-ai-engineer/tree/pre-session-04.

La subida autorizada corresponde al repositorio GitHub. El envío del enlace
al facilitador se realiza por separado.
