from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from src.latex_escape import escape_for_latex
from src.schemas import CVContent


TEMPLATE_DIR = Path("templates")


def render_latex(profile: dict[str, Any], content: CVContent, template_name: str = "ats_one_page.tex.j2") -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )
    template = env.get_template(template_name)
    escaped_profile = escape_for_latex(profile)
    escaped_content = escape_for_latex(content.model_dump())
    return template.render(profile=escaped_profile, cv=escaped_content)


def write_latex(
    profile: dict[str, Any],
    content: CVContent,
    output_path: Path,
    template_name: str = "ats_one_page.tex.j2",
) -> Path:
    output_path.write_text(render_latex(profile, content, template_name), encoding="utf-8")
    return output_path
