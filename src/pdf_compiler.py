from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class PDFCompilationError(RuntimeError):
    pass


def compile_pdf(tex_path: Path) -> Path:
    if not shutil.which("tectonic"):
        raise PDFCompilationError("Tectonic is not installed or is not available on PATH.")
    result = subprocess.run(
        ["tectonic", tex_path.name],
        cwd=tex_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    pdf_path = tex_path.with_suffix(".pdf")
    if result.returncode != 0 or not pdf_path.exists():
        raise PDFCompilationError(result.stderr or result.stdout or "Tectonic failed without output.")
    return pdf_path
