"""Estimaciones ficticias de referencia para el contexto CAG."""

ESTIMATION_EXAMPLES = [
    {
        "meeting_summary": (
            "El cliente necesita una aplicación web para gestionar el "
            "inventario de un almacén. Quiere registrar productos, entradas "
            "y salidas, recibir alertas de stock bajo y consultar métricas. "
            "Habrá dos roles: administrador y operador. No requiere "
            "integración con ERP ni aplicación móvil."
        ),
        "estimation": """
## Estimación: Plataforma de gestión de inventario

### Alcance y supuestos
- Un almacén y dos roles de usuario.
- Aplicación web adaptable a escritorio y móvil.
- Alertas de stock bajo dentro de la aplicación.
- El cliente proporcionará el catálogo inicial en un formato acordado.
- Tarifa ficticia uniforme: 500 MXN/hora.

### Desglose de tareas
| Tarea | Horas | Coste (MXN) |
|---|---:|---:|
| Definición de requisitos y modelo de datos | 16 | 8,000 |
| Diseño UI/UX | 24 | 12,000 |
| Backend: productos y movimientos de inventario | 40 | 20,000 |
| Autenticación y roles | 20 | 10,000 |
| Frontend: gestión de inventario | 32 | 16,000 |
| Dashboard y alertas de stock | 16 | 8,000 |
| Pruebas y correcciones | 24 | 12,000 |
| Despliegue y documentación | 8 | 4,000 |

### Totales
- Esfuerzo base: 180 horas.
- Coste base: 90,000 MXN.
- Reserva de contingencia (20%): 36 horas / 18,000 MXN.
- Total con contingencia: 216 horas / 108,000 MXN.

### Equipo y duración
- 1 desarrollador full-stack y 1 diseñador UX con dedicación parcial.
- Duración orientativa: 7-9 semanas, con unas 30 horas efectivas
  de trabajo combinado por semana y revisiones del cliente.

### Exclusiones y riesgos
- No incluye ERP, aplicación móvil nativa ni limpieza de datos históricos.
- Hosting, licencias e impuestos no están incluidos.
- Cambios en las reglas de inventario requieren revisar la estimación.
""".strip(),
    },
    {
        "meeting_summary": (
            "El cliente necesita una aplicación web de reservas para una "
            "consultoría. Sus clientes deben consultar horarios, reservar "
            "y cancelar citas. El personal administrará disponibilidad "
            "y servicios. Se enviarán correos de confirmación. "
            "No habrá pagos en línea ni sincronización con calendarios externos."
        ),
        "estimation": """
## Estimación: Sistema de reservas de citas

### Alcance y supuestos
- Una sede con hasta cinco consultores.
- Duración fija por servicio y una sola zona horaria.
- Roles de cliente y administrador.
- Confirmaciones por correo mediante un proveedor externo.
- Tarifa ficticia uniforme: 500 MXN/hora.

### Desglose de tareas
| Tarea | Horas | Coste (MXN) |
|---|---:|---:|
| Definición de requisitos y reglas de reserva | 16 | 8,000 |
| Diseño UI/UX | 20 | 10,000 |
| Autenticación y roles | 16 | 8,000 |
| Backend: disponibilidad, reservas y cancelaciones | 40 | 20,000 |
| Frontend: consulta de horarios y reservas | 32 | 16,000 |
| Panel de administración | 24 | 12,000 |
| Integración de correos de confirmación | 12 | 6,000 |
| Pruebas, incluidas reservas simultáneas | 24 | 12,000 |
| Despliegue y documentación | 8 | 4,000 |

### Totales
- Esfuerzo base: 192 horas.
- Coste base: 96,000 MXN.
- Reserva de contingencia (25%): 48 horas / 24,000 MXN.
- Total con contingencia: 240 horas / 120,000 MXN.

### Equipo y duración
- 1 desarrollador full-stack y 1 diseñador UX con dedicación parcial.
- Duración orientativa: 8-10 semanas, con unas 30 horas efectivas
  de trabajo combinado por semana y revisiones del cliente.

### Exclusiones y riesgos
- No incluye pagos, SMS ni sincronización con calendarios externos.
- Hosting, servicio de correo e impuestos no están incluidos.
- La contingencia contempla ajustes en disponibilidad y concurrencia.
- Cambios en las políticas de cancelación requieren revisar la estimación.
""".strip(),
    },
]