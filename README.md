# LIDR AI Engineer

Repositorio de prácticas del curso LIDR AI Engineer.

Cada práctica contiene mi implementación, documentación del proceso,
datos de ejemplo y, cuando esté disponible y su licencia lo permita,
una solución de referencia del curso.

## Prácticas

| Práctica | Tema | Carpeta |
|---|---|---|
| 01 | Estimador de software con FastAPI y contexto estático CAG | [Ver práctica](practicas/01-estimador-cag/) |

## Organización

- `mi-proyecto/`: implementación realizada durante la práctica.
- `solucion-referencia/`: solución del curso, cuando se incorpore.
- La documentación de cada práctica describe los pasos, decisiones,
  problemas encontrados y verificaciones realizadas.

## Credenciales

Las claves API se configuran localmente mediante un archivo `.env`.
Este archivo no se incluye en Git.

Cada proyecto proporciona un `.env.example` sin credenciales reales.

## Validación automática

El workflow `.github/workflows/validate.yml` valida la práctica 01 en cada
push y pull request. También permite ejecución manual desde Actions.
Ejecuta pruebas con el proveedor LLM simulado, sin consumir créditos.
La primera ejecución en GitHub queda pendiente del primer push.

Consulta [la explicación del pipeline](practicas/01-estimador-cag/validacion-automatica.md).
