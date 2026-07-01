from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


LATEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(value: str) -> str:
    return "".join(LATEX_REPLACEMENTS.get(char, char) for char in value)


def escape_for_latex(value: Any) -> Any:
    if isinstance(value, str):
        return escape_latex(value)
    if isinstance(value, Mapping):
        return {key: escape_for_latex(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [escape_for_latex(item) for item in value]
    return value
