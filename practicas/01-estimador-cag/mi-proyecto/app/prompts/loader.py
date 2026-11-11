from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.schemas.estimation import EstimationRequest
from app.schemas.session import SessionRequest
from app.sessions import ProjectMetadata


environment = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
)


def render_estimation_prompt(
    request: EstimationRequest, version: str = "v1"
) -> tuple[str, str]:
    """Devuelve instrucciones y datos separados para el proveedor."""
    if re.fullmatch(r"v[1-9][0-9]*", version) is None:
        raise ValueError("La versión debe tener el formato v1, v2, etc.")
    context = request.model_dump(mode="json")
    context["prompt_version"] = version
    folder = f"estimation/{version}"
    system = environment.get_template(f"{folder}/system.j2").render(**context)
    user = environment.get_template(f"{folder}/user.j2").render(**context)
    return system, user


def render_conversational_prompt(
    request: SessionRequest, metadata: ProjectMetadata, version: str = "v2",
) -> tuple[str, str]:
    if re.fullmatch(r"v[1-9][0-9]*", version) is None:
        raise ValueError("La versión debe tener el formato v1, v2, etc.")
    context = request.model_dump(mode="json")
    # JSON escapa delimitadores XML para mantener el bloque reconocible.
    context["metadata_json"] = "" if metadata.is_empty() else (
        metadata.model_dump_json().replace("<", "\\u003c").replace(">", "\\u003e")
    )
    folder = f"estimation/{version}"
    return (
        environment.get_template(f"{folder}/system.j2").render(**context),
        environment.get_template(f"{folder}/user.j2").render(**context),
    )
