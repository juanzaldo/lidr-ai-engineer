"""Heurística deliberadamente limitada: hechos explícitos, sin otra llamada LLM."""

import re

from app.schemas.estimation import EstimationResult
from app.sessions import ProjectMetadata


TECHNOLOGIES = {
    "Python": r"python", "FastAPI": r"fastapi", "Django": r"django",
    "React": r"react", "Vue": r"vue", "Angular": r"angular",
    "PostgreSQL": r"postgres(?:ql)?", "MySQL": r"mysql", "Redis": r"redis",
    "Node.js": r"node(?:\.js)?", "TypeScript": r"typescript",
    "JavaScript": r"javascript", "Docker": r"docker", "AWS": r"aws",
    "Azure": r"azure", "Stripe": r"stripe", "Flutter": r"flutter",
    "Java": r"java", "Kotlin": r"kotlin", "Swift": r"swift",
}


def last_match(pattern: str, text: str) -> str | None:
    matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
    return matches[-1].group(1).strip().strip('"\'') if matches else None


def update_metadata(
    previous: ProjectMetadata, transcript: str, result: EstimationResult,
) -> ProjectMetadata:
    """Actualiza después de una respuesta válida, sin mutar el estado anterior.

    Nombre/alcance/tecnologías proceden del cliente o sus documentos. Solo se
    toma del modelo un tamaño de equipo etiquetado explícitamente como supuesto
    cuando todavía no se conoce. No convierte sus propuestas en alcance acordado.
    Las paráfrasis libres y negaciones complejas requieren revisión del usuario.
    """
    original, separator, documents = transcript.partition("\n\n--- attachment: ")
    if separator:
        # Los hechos explícitos del turno prevalecen sobre propuestas adjuntas.
        transcript = documents + "\n" + original
    data = previous.model_dump()
    name = last_match(r"(?:nombre del proyecto|proyecto)\s*:\s*([^\n.;]+)", transcript)
    if name is None:
        name = last_match(
            r"(?:se llama|llamado)\s+[\"']?(.+?)(?=\s+(?:en|con|para)\s|[\n.;]|$)",
            transcript,
        )
    if name and len(name) <= 120:
        data["project_name"] = name
    team = last_match(r"(?:equipo(?: asumido)?\s*:\s*|equipo de\s+)(\d+)\b", transcript)
    if team is None and previous.assumed_team_size is None:
        team = last_match(r"equipo asumido\s*:\s*(\d+)\b", result.summary)
    if team and 1 <= int(team) <= 50:
        data["assumed_team_size"] = int(team)

    scope = last_match(r"alcance(?: acordado)?\s*:\s*([^\n]+)", transcript)
    if scope:
        data["agreed_scope"] = scope[:2000]
    additions = re.findall(r"\b(?:añade|agrega|incluye)\s+([^\n.]+)", original, re.I)
    for addition in additions:
        old = data["agreed_scope"] or ""
        if addition.casefold() not in old.casefold():
            data["agreed_scope"] = f"{old}; {addition}".strip("; ")[:2000]

    # Unión de menciones; 'sin X' y 'no usar X' eliminan una tecnología previa.
    technologies = list(data["mentioned_technologies"])
    for canonical, pattern in TECHNOLOGIES.items():
        occurrences = list(re.finditer(rf"\b(?:{pattern})\b", transcript, re.I))
        if not occurrences:
            continue
        prefix = transcript[max(0, occurrences[-1].start() - 35):occurrences[-1].start()]
        negative = re.search(r"(?:sin|no (?:usar|usaremos|utilizar)|elimina)\s+$", prefix, re.I)
        technologies = [tech for tech in technologies if tech.casefold() != canonical.casefold()]
        if not negative:
            technologies.append(canonical)
    data["mentioned_technologies"] = technologies
    return ProjectMetadata.model_validate(data)
